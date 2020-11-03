import * as cdk from '@aws-cdk/core';
import * as ec2 from '@aws-cdk/aws-ec2';
import * as rds from '@aws-cdk/aws-rds';

interface Props extends cdk.StackProps {
  vpc: ec2.IVpc;
}

export class RdsStack extends cdk.Stack {
  constructor(scope: cdk.Construct, id: string, props: Props) {
    super(scope, id, props);

    const ingressCIDR = scope.node.tryGetContext('ingressCIDR');
    const cluster = this.createCluster(props, ingressCIDR);
    this.putParams(cluster);
  }

  createCluster(props: Props, ingressCIDR: string): rds.DatabaseCluster {
    const cluster = new rds.DatabaseCluster(this, `RdsCluster`, {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_11_7,
      }),
      credentials: rds.Credentials.fromUsername('postgres'),
      instances: 1,
      instanceProps: {
        vpc: props.vpc,
        vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
        instanceType: ec2.InstanceType.of(ec2.InstanceClass.R5, ec2.InstanceSize.LARGE),
      },
      port: 5432,
      defaultDatabaseName: 'pgdb',
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      parameterGroup: rds.ParameterGroup.fromParameterGroupName(
        this,
        `RdsParameterGroup`,
        'default.aurora-postgresql11'
      ),
    });
    cluster.addRotationSingleUser();
    cluster.connections.allowDefaultPortInternally();
    cluster.connections.allowDefaultPortFrom(ec2.Peer.ipv4(props.vpc.vpcCidrBlock));
    cluster.connections.allowDefaultPortFrom(ec2.Peer.ipv4(ingressCIDR));

    return cluster;
  }

  putParams(cluster: rds.DatabaseCluster): void {
    new cdk.CfnOutput(this, `SecretArn`, {
      exportName: 'SecretArn',
      value: cluster.secret!.secretArn,
    });
  }

}