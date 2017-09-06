# quickstart-git2s3
## Git webhooks with AWS services
### Linking your Git repository to Amazon S3 and AWS services for continuous code integration, testing, and deployment 

This Quick Start deploys HTTPS endpoints and AWS Lambda functions for implementing webhooks, to enable event-driven integration between Git services and Amazon Web Services (AWS) on the AWS Cloud.

After you deploy the Quick Start, you can set up a webhook that uses the endpoints to create a bridge between your on-premises Git repository and AWS services like AWS CodePipeline and AWS CodeBuild. With this setup, builds and pipeline executions occur automatically when you commit your code to a Git repository, and your code can be continuously integrated, tested, built, and deployed on AWS with each change. 

The Quick Start includes an AWS CloudFormation template that automates the deployment. You can also use the AWS CloudFormation template as a starting point for your own implementation.

![Quick Start architecture for implementing webhooks on AWS](https://d0.awsstatic.com/partner-network/QuickStart/datasheets/git-to-s3-webhooks-architecture-on-aws.png)

For implementation details, deployment instructions, and customization options, see the [deployment guide](https://s3.amazonaws.com/quickstart-reference/git2s3/latest/doc/git-to-amazon-s3-using-webhooks.pdf).

To post feedback, submit feature ideas, or report bugs, use the **Issues** section of this GitHub repo.
If you'd like to submit code for this Quick Start, please review the [AWS Quick Start Contributor's Kit](https://aws-quickstart.github.io/). 
