#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from '@aws-cdk/core';
import { VpcStack } from '../lib/vpc-stack';
import { RdsStack } from '../lib/rds-stack';

const ns = 'Demo';
const app = new cdk.App({
  context: {
    ns,
    ingressCIDR: '39.115.51.138/32',
  },
});

const vpcStack = new VpcStack(app, `VpcStack${ns}`);

const rdsStack = new RdsStack(app, `RdsStack${ns}`, {
  vpc: vpcStack.vpc,
});
rdsStack.addDependency(vpcStack);
