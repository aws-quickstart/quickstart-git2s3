#  Copyright 2020 Amazon Web Services, Inc. or its affiliates.
#  All Rights Reserved.
#  This file is licensed to you under the AWS Customer Agreement
#  (the "License").
#  You may not use this file except in compliance with the License.
#  A copy of the License is located at http://aws.amazon.com/agreement/ .
#  This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
#  CONDITIONS OF ANY KIND, express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


import cfnresponse
import traceback
import boto3
from cryptography.hazmat.primitives import serialization as \
    crypto_serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend as \
    crypto_default_backend


def lambda_handler(event,context):
    try:
        if event['RequestType'] == 'Create':
            # Generate keys
            new_key = rsa.generate_private_key(
                backend=crypto_default_backend(), public_exponent=65537,
                key_size=2048)
            priv_key = str(new_key.private_bytes(
                crypto_serialization.Encoding.PEM,
                crypto_serialization.PrivateFormat.PKCS8,
                crypto_serialization.NoEncryption()
            ), 'utf-8')
            pub_key = str(new_key.public_key().public_bytes(
                crypto_serialization.Encoding.OpenSSH,
                crypto_serialization.PublicFormat.OpenSSH
            ), 'utf-8')
            print(priv_key)
            print(pub_key)
            # Encrypt private key
            kms = boto3.client(
                'kms', region_name=event["ResourceProperties"]["Region"])
            enc_key = kms.encrypt(
                KeyId=event["ResourceProperties"]["KMSKey"],
                Plaintext=priv_key)['CiphertextBlob']
            f = open('/tmp/enc_key', 'wb')
            f.write(enc_key)
            f.close()
            # Upload private key to S3
            s3 = boto3.client('s3')
            s3.upload_file('/tmp/enc_key',
                           event["ResourceProperties"]["KeyBucket"], 'enc_key')
        else:
            pub_key = event['PhysicalResourceId']
        cfnresponse.send(event, context, cfnresponse.SUCCESS, {}, pub_key)
    except:
        traceback.print_exc()
        cfnresponse.send(event, context, cfnresponse.FAILED, {}, '')

