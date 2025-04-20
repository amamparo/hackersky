from os import getcwd

from aws_cdk import Stack, App, Duration
from aws_cdk.aws_ec2 import SubnetSelection, SubnetType
from aws_cdk.aws_ecr_assets import Platform
from aws_cdk.aws_events import Schedule, Rule
from aws_cdk.aws_events_targets import LambdaFunction
from aws_cdk.aws_lambda import DockerImageFunction, DockerImageCode, Architecture
from aws_cdk.aws_secretsmanager import Secret
from constructs import Construct

class Hackersky(Stack):
    def __init__(self, scope: Construct):
        super().__init__(scope, 'Hackersky',
                         description='A Bluesky bot that posts trending news.ycombinator.com articles')

        secret = Secret(self, 'Secret')

        function = DockerImageFunction(
            self,
            'Function',
            memory_size=128,
            code=DockerImageCode.from_image_asset(
                directory=getcwd(),
                platform=Platform.LINUX_ARM64,
                cmd=['src.main.lambda_handler']
            ),
            architecture=Architecture.ARM_64,
            environment={
                'SECRET_ARN': secret.secret_arn,
                'NAME': 'Alice'
            },
            timeout=Duration.minutes(15),
            vpc_subnets=SubnetSelection(subnet_type=SubnetType.PRIVATE_WITH_EGRESS)
        )

        secret.grant_read(function)

        Rule(self, 'Schedule', schedule=Schedule.rate(Duration.hours(1))).add_target(LambdaFunction(function))


if __name__ == '__main__':
    app = App()
    Hackersky(app)
    app.synth()
