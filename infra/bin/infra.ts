#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from '@aws-cdk/core';
import { VpcStack } from '../lib/vpc-stack';
import { RdsStack } from '../lib/rds-stack';

const ns = 'Demo';
const app = new cdk.App({
  context: {
    ns,
    ingressCIDR: '54.239.119.16/32',
  },
});

const vpcStack = new VpcStack(app, `${ns}VpcStack`);

const rdsStack = new RdsStack(app, `${ns}RdsStack`, {
  vpc: vpcStack.vpc,
});
rdsStack.addDependency(vpcStack);
