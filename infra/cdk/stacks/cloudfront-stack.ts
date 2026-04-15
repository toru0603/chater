import * as cdk from 'aws-cdk-lib';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import { Construct } from 'constructs';

export interface CloudFrontStackProps extends cdk.StackProps {
  /** Full URL of the prod API Gateway (e.g. https://xxxx.execute-api.ap-northeast-1.amazonaws.com/prod/) */
  prodApiUrl: string;
  /** Full URL of the dev API Gateway (e.g. https://xxxx.execute-api.ap-northeast-1.amazonaws.com/dev/) */
  devApiUrl: string;
}

export class CloudFrontStack extends cdk.Stack {
  public readonly distributionDomainName: string;

  constructor(scope: Construct, id: string, props: CloudFrontStackProps) {
    super(scope, id, props);

    const prodApiDomain = new URL(props.prodApiUrl).hostname;
    const devApiDomain = new URL(props.devApiUrl).hostname;

    const prodOrigin = new origins.HttpOrigin(prodApiDomain, {
      protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
    });

    const devOrigin = new origins.HttpOrigin(devApiDomain, {
      protocolPolicy: cloudfront.OriginProtocolPolicy.HTTPS_ONLY,
    });

    const behaviorOptions: cloudfront.BehaviorOptions = {
      origin: prodOrigin,
      cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
      originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
      allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    };

    const distribution = new cloudfront.Distribution(this, 'ChaterDistribution', {
      comment: 'Chater: routes /prod/* to prod API, /dev/* to dev API',
      defaultBehavior: behaviorOptions,
      additionalBehaviors: {
        '/prod/*': {
          ...behaviorOptions,
          origin: prodOrigin,
        },
        '/dev/*': {
          ...behaviorOptions,
          origin: devOrigin,
        },
      },
    });

    this.distributionDomainName = distribution.distributionDomainName;

    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      value: `https://${distribution.distributionDomainName}`,
      description: 'CloudFront distribution URL',
    });

    new cdk.CfnOutput(this, 'ProdUrl', {
      value: `https://${distribution.distributionDomainName}/prod/`,
      description: 'Prod environment URL via CloudFront',
    });

    new cdk.CfnOutput(this, 'DevUrl', {
      value: `https://${distribution.distributionDomainName}/dev/`,
      description: 'Dev environment URL via CloudFront',
    });
  }
}
