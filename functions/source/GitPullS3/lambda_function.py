#  Copyright 2016 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
#  This file is licensed to you under the AWS Customer Agreement (the "License").
#  You may not use this file except in compliance with the License.
#  A copy of the License is located at http://aws.amazon.com/agreement/ .
#  This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, express or implied.
#  See the License for the specific language governing permissions and limitations under the License.

from boto3 import client
import os
import time
import stat
import shutil
from ipaddress import ip_network, ip_address
import logging
import hmac
import hashlib
import distutils.util

# If true the function will not include .git folder in the zip
exclude_git = bool(distutils.util.strtobool(os.environ['ExcludeGit']))

# If true the function will delete all files at the end of each invocation, useful if you run into storage space
# constraints, but will slow down invocations as each invoke will need to checkout the entire repo
cleanup = False

key = 'enc_key'

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.handlers[0].setFormatter(logging.Formatter('[%(asctime)s][%(levelname)s] %(message)s'))
logging.getLogger('boto3').setLevel(logging.ERROR)
logging.getLogger('botocore').setLevel(logging.ERROR)

s3 = client('s3')
kms = client('kms')


def lambda_handler(event, context):
    print(event)
    keybucket = event['context']['key-bucket']
    outputbucket = event['context']['output-bucket']
    pubkey = event['context']['public-key']
    # Source IP ranges to allow requests from, if the IP is in one of these the request will not be chacked for an api key
    ipranges = []
    if event['context']['allowed-ips']:
        for i in event['context']['allowed-ips'].split(','):
            ipranges.append(ip_network(u'%s' % i))
    # APIKeys, it is recommended to use a different API key for each repo that uses this function
    apikeys = event['context']['api-secrets'].split(',')
    ip = ip_address(event['context']['source-ip'])
    secure = False
    if ipranges:
        for net in ipranges:
            if ip in net:
                secure = True
    if 'X-Git-Token' in event['params']['header'].keys():
        print (event['params']['header']['X-Git-Token'])
        if event['params']['header']['X-Git-Token'] in apikeys:
            secure = True
    if 'X-Gitlab-Token' in event['params']['header'].keys():
        if event['params']['header']['X-Gitlab-Token'] in apikeys:
            secure = True
    if 'X-Hub-Signature' in event['params']['header'].keys():
        for k in apikeys:
            if 'use-sha256' in event['context']:
                k1 = hmac.new(str(k).encode('utf-8'), str(event['context']['raw-body']).encode('utf-8'), hashlib.sha256).hexdigest()
                k2 = str(event['params']['header']['X-Hub-Signature'].replace('sha256=', ''))
            else:
                k1 = hmac.new(str(k).encode('utf-8'), str(event['context']['raw-body']).encode('utf-8'), hashlib.sha1).hexdigest()
                k2 = str(event['params']['header']['X-Hub-Signature'].replace('sha1=', ''))
            if k1 == k2:
                secure = True
    # TODO: Add the ability to clone TFS repo using SSH keys
    try:
        # GitHub
        full_name = event['body-json']['repository']['full_name']
    except KeyError:
        try:
            # BitBucket #14
            full_name = event['body-json']['repository']['fullName']
        except KeyError:
            try:
                # GitLab
                full_name = event['body-json']['repository']['path_with_namespace']
            except KeyError:
                try:
                    # GitLab 8.5+
                    full_name = event['body-json']['project']['path_with_namespace']
                except KeyError:
                    try:
                        # BitBucket server
                        full_name = event['body-json']['repository']['name']
                    except KeyError:
                        # BitBucket pull-request
                        full_name = event['body-json']['pullRequest']['fromRef']['repository']['name']
    if not secure:
        logger.error('Source IP %s is not allowed' % event['context']['source-ip'])
        raise Exception('Source IP %s is not allowed' % event['context']['source-ip'])

    # GitHub publish event
    if('action' in event['body-json'] and event['body-json']['action'] == 'published'):
        branch_name = 'tags/%s' % event['body-json']['release']['tag_name']
        repo_name = full_name + '/release'
    else:
        repo_name = full_name
        try:
            # branch names should contain [name] only, tag names - "tags/[name]"
            branch_name = event['body-json']['ref'].replace('refs/heads/', '').replace('refs/tags/', 'tags/')
        except KeyError:
            try:
                # Bibucket server
                branch_name = event['body-json']['push']['changes'][0]['new']['name']
            except:
                branch_name = 'master'
    try:
        # GitLab
        remote_url = event['body-json']['project']['git_ssh_url']
    except Exception:
        try:
            remote_url = 'git@'+event['body-json']['repository']['links']['html']['href'].replace('https://', '').replace('/', ':', 1)+'.git'
        except:
            try:
                # GitHub
                remote_url = event['body-json']['repository']['ssh_url']
            except:
                # Bitbucket
                try:
                    for i, url in enumerate(event['body-json']['repository']['links']['clone']):
                        if url['name'] == 'ssh':
                            ssh_index = i
                    remote_url = event['body-json']['repository']['links']['clone'][ssh_index]['href']
                except:
                    # BitBucket pull-request
                    for i, url in enumerate(event['body-json']['pullRequest']['fromRef']['repository']['links']['clone']):
                        if url['name'] == 'ssh':
                            ssh_index = i

                    remote_url = event['body-json']['pullRequest']['fromRef']['repository']['links']['clone'][ssh_index]['href']
    try:
        codebuild_client = client(service_name='codebuild')
        new_build = codebuild_client.start_build(projectName=os.getenv('GitPullCodeBuild'),
                                    environmentVariablesOverride=[
                                        {
                                            'name': 'GitUrl',
                                            'value': remote_url,
                                            'type': 'PLAINTEXT'
                                        },
                                        {
                                            'name': 'Branch',
                                            'value': branch_name,
                                            'type': 'PLAINTEXT'
                                        },
                                        {
                                            'name': 'KeyBucket',
                                            'value': keybucket,
                                            'type': 'PLAINTEXT'
                                        },
                                        {
                                            'name': 'KeyObject',
                                            'value': key,
                                            'type': 'PLAINTEXT'
                                        },

                                        {
                                            'name': 'outputbucket',
                                            'value': outputbucket,
                                            'type': 'PLAINTEXT'
                                        },
                                        {
                                            'name': 'outputbucketkey',
                                            'value': '%s' % (repo_name.replace('/', '_')) + '.zip',
                                            'type': 'PLAINTEXT'
                                        },
                                        {
                                            'name': 'outputbucketpath',
                                            'value': '%s/%s/' % (repo_name, branch_name),
                                            'type': 'PLAINTEXT'
                                        },
                                        {
                                            'name': 'exclude_git',
                                            'value': '%s' % (exclude_git),
                                            'type': 'PLAINTEXT'
                                        }
                                        
                                    ])
        buildId = new_build['build']['id']
        logger.info('CodeBuild Build Id is %s' % (buildId))
        buildStatus = 'NOT_KNOWN'
        counter = 0
        while (counter < 60 and buildStatus != 'SUCCEEDED'):  # capped this, so it just fails if it takes too long
            logger.info("Waiting for Codebuild to complete")
            time.sleep(5)
            logger.info(counter)
            counter = counter + 1
            theBuild = codebuild_client.batch_get_builds(ids=[buildId])
            print(theBuild)
            buildStatus = theBuild['builds'][0]['buildStatus']
            logger.info('CodeBuild Build Status is %s' % (buildStatus))
            if buildStatus == 'SUCCEEDED':
                EnvVariables = theBuild['builds'][0]['exportedEnvironmentVariables']
                commit_id = [env for env in EnvVariables if env['name'] == 'GIT_COMMIT_ID'][0]['value']
                commit_message = [env for env in EnvVariables if env['name'] == 'GIT_COMMIT_MSG'][0]['value'] 
                current_revision = {
                                    'revision': "Git Commit Id:" + commit_id,
                                    'changeIdentifier': 'GitLab',
                                    'revisionSummary': "Git Commit Message:" + commit_message
                                    }
                outputVariables = {
                    'commit_id': "Git Commit Id:" + commit_id,
                    'commit_message': "Git Commit Message:" + commit_message
                }
                break
            elif buildStatus == 'FAILED' or buildStatus == 'FAULT' or buildStatus == 'STOPPED' or buildStatus == 'TIMED_OUT':
                break
    except Exception as e:
        logger.info("Error in Function: %s" % (e))
