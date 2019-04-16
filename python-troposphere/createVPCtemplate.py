from troposphere import Template, Parameter, Ref, GetAtt, Output,\
    Base64, Join
import os
from troposphere.ec2 import VPC, Subnet, Instance,\
    InternetGateway, Tags, VPCGatewayAttachment, EIP,\
    SecurityGroup, SecurityGroupRule, SecurityGroupIngress, NetworkInterfaceProperty,\
    RouteTable, Route, SubnetRouteTableAssociation, \
    NetworkAcl, NetworkAclEntry, SubnetNetworkAclAssociation,PortRange,\
    NatGateway, EIPAssociation

# Q&A
# 1. Tags and Output
# 2. Change Set Before Updating the stacks
# 3. What's the best way to handle security groups? 1 security group per instance?

# Object that will generate the template
t = Template()

#### Define AWS Environment ####
ImageID = "ami-024fe7d8b3a587508"

ref_stack_id = Ref('AWS::StackId')
ref_stack_name = Ref('AWS::StackName')

#### Parameters ####

# SSH Key parameter
ssh_keyname_param = t.add_parameter(
    Parameter(
        "cpSSHKey",
        Description="Name of an existing EC2 SSH KeyPair",
        Type="AWS::EC2::KeyPair::KeyName"
    )
)


#### Resources ####

# Define VPC 10.0.0.0/16
VPC = t.add_resource(
    VPC(
        'cpVPC',
        CidrBlock='10.0.0.0/16',
        EnableDnsSupport='true',
        EnableDnsHostnames='true',
        Tags=Tags(
            Application=ref_stack_id)
    )
)

# Define public Subnet 10.0.0.0/24
# !!! it's a subnet with a route table that has a route to a InternetGateway !!!
publicSubnet = t.add_resource(
    Subnet(
        'cpPublicSubnet',
        CidrBlock='10.0.0.0/24',
        VpcId=Ref(VPC),
        MapPublicIpOnLaunch='true',  # assigns public IP's to the EC2's
        Tags=Tags(
            Application=ref_stack_id)
    )
)

# Define private Subnet 10.0.1.0/24
privateSubnet = t.add_resource(
    Subnet(
        'cpPrivateSubnet',
        CidrBlock='10.0.1.0/24',
        VpcId=Ref(VPC),
        Tags=Tags(
            Application=ref_stack_id)
    )
)

# Define route table for private subnet
private_route_table = t.add_resource(
    RouteTable(
        "cpPrivateRouteTable",
        VpcId=Ref(VPC)
    )
)

# Define route table for public subnet
public_route_table = t.add_resource(
    RouteTable(
        "cpPublicRouteTable",
        VpcId=Ref(VPC)
    )
)

# Associate the Routing Table to the private Subnet
private_route_table_association = t.add_resource(
    SubnetRouteTableAssociation(
        "cpPrivateSubnetRouteTableAssociation01",
        RouteTableId=Ref(private_route_table),
        SubnetId=Ref(privateSubnet)
    )
)

# Associate the Routing Table to the public Subnet
public_route_table_association = t.add_resource(
    SubnetRouteTableAssociation(
        "cpPublicSubnetRouteTableAssociation01",
        RouteTableId=Ref(public_route_table),
        SubnetId=Ref(publicSubnet)
    )
)

############## Routes #################

# Define Internet Gateway
internetGateway = t.add_resource(
    InternetGateway(
        'cpInternetGateway',
        Tags=Tags(
            Application=ref_stack_id)
    )
)

# Attach InternetGateway to VPC
gatewayAttachment = t.add_resource(
    VPCGatewayAttachment(
        'cpAttachInternetGateway',
        VpcId=Ref(VPC),
        InternetGatewayId=Ref(internetGateway)
    )
)

# route from the public subnet to the Internet Gateway
publicToInternetGatewayRoute = t.add_resource(
    Route(
        "cpInternetGatewayRoute",
        RouteTableId=Ref(public_route_table),
        GatewayId=Ref(internetGateway),
        DestinationCidrBlock='0.0.0.0/0'
    )
)


# Allocate EIP - will be used for NAT Gateway
natEIP = t.add_resource(
    EIP(
        "NATGatewayElasticIP",
        Domain='vpc'
    )
)

natGateway = t.add_resource(
    NatGateway(
        "NATGateway",
        AllocationId=GetAtt(natEIP, 'AllocationId'),
        SubnetId=Ref(publicSubnet)
    )
)

# route from the private subnet to the NAT Gateway
privateToNATRoute = t.add_resource(
    Route(
        "cpNATRoute",
        RouteTableId=Ref(private_route_table),
        NatGatewayId=Ref(natGateway),
        DestinationCidrBlock='0.0.0.0/0'
    )
)

# Allocate WebServer EIP
webServerEIP = t.add_resource(
    EIP(
        "webServerElasticIP",
        Domain='vpc'
    )
)



'''
# Define Network ACL on Subnet Level
networkAcl = t.add_resource(
    NetworkAcl(
        "cpNetworkAcl",
        VpcId=Ref(VPC)
    )
)

networkAclEntry01 = t.add_resource(
    NetworkAclEntry(
        "cpSSHInboundNetworkAclEntry",
        NetworkAclId=Ref(networkAcl),
        Protocol=6,
        CidrBlock='0.0.0.0/0',
        Egress='false',
        PortRange=PortRange(
            From='22',
            To='22'),
        RuleAction='allow',
        RuleNumber='1'
    )
)

subnetNetworkAclAssociation = t.add_resource(
    SubnetNetworkAclAssociation(
        "cpPublicSubnetNetworkAclAssociation",
        SubnetId=Ref(publicSubnet),
        NetworkAclId=Ref(networkAcl)
    )
)

'''

# Define Security Group for
# - allows Inbound SSH access - Port 22

# NOT NECESSARY to have such fine-grained security? (Ilie)
webServerSecurityGroup = t.add_resource(
    SecurityGroup(
        'cpWebServerSecurityGroup',
        GroupDescription='Web Server Security Group',
        VpcId=Ref(VPC),
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='22',
                ToPort='22',
                CidrIp='0.0.0.0/0'
            ),
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='80',
                ToPort='80',
                CidrIp='0.0.0.0/0'
            ),
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='81',
                ToPort='81',
                CidrIp='0.0.0.0/0'
            )
        ]
    )
)

backendSecurityGroup = t.add_resource(
    SecurityGroup(
        'cpBackendSecurityGroup',
        GroupDescription='Backend Server Security Group',
        VpcId=Ref(VPC),
        SecurityGroupIngress=[
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='22',
                ToPort='22',
                CidrIp='0.0.0.0/0'
            ),
            SecurityGroupRule(
                IpProtocol='tcp',
                FromPort='8081',
                ToPort='8081',
                CidrIp='0.0.0.0/0'
            )
        ]
    )
)


# Define EC2 instances
# - 2 in the public subnet
# - 2 in the private subnet
pubInst01 = t.add_resource(
    Instance(
        'cpPubInstance01',
        ImageId=ImageID,
        InstanceType='t2.micro',
        Tags=[{"Key": "Name", "Value": "cp_public_instance_1"}],
        KeyName=Ref(ssh_keyname_param),
        NetworkInterfaces=[
            NetworkInterfaceProperty(
                GroupSet=[
                    Ref(webServerSecurityGroup)],
                DeviceIndex='0',
                DeleteOnTermination='true',
                SubnetId=Ref(publicSubnet)
            )
        ]
    )
)


'''
                
                '''

privInst01 = t.add_resource(
    Instance(
        'cpPrivInstance01',
        ImageId=ImageID,
        InstanceType='t2.micro',
        Tags=[{"Key": "Name", "Value": "cp_priv_instance_1"}],
        KeyName=Ref(ssh_keyname_param),
        NetworkInterfaces=[
            NetworkInterfaceProperty(
                GroupSet=[
                    Ref(backendSecurityGroup)],
                DeviceIndex='0',
                DeleteOnTermination='true',
                SubnetId=Ref(privateSubnet)
            )
        ],
        UserData=Base64(
            Join('', [
                '#!/bin/bash -v\n',
                "sudo yum install -y https://dl.fedoraproject.org/pub/epel/epel-release-latest-$(rpm -E '%{rhel}').noarch.rpm &>/root/user-data.log\n",
                'sudo yum install -y python-pip &>>/root/user-data.log\n',
                'sudo pip install Flask &>>/root/user-data.log\n',
                'sudo yum install -y git &>>/root/user-data.log\n',
                'sudo mkdir -p /root/work && cd /root/work/ && git clone -v https://github.com/cjurju/pikachuFly.git . &>>/root/user-data.log\n',
                'sudo python /root/work/python-troposphere/HelloWorld.py &>>/root/user-data.log'
            ]))
    )
)

# Associate the EIP to the webServer EC2 instance
webServerEIPAssociation = t.add_resource(
    EIPAssociation(
        "webServerEIPAssociation",
        AllocationId=GetAtt(webServerEIP, 'AllocationId'),
        InstanceId=Ref(pubInst01)
    )
)

#### Outputs ####

t.add_output([
    Output(
        "webServerEIP",
        Description="Elastic IP of the web server EC2",
        Value=GetAtt(webServerEIP,'AllocationId')
    )
])

print(t.to_json())

# Delete output file if already exists
os.remove('/Users/camelia.pohoata/IdeaProjects/FlyPikachu/python-troposphere/templates/template01.json')

# Write template to file
fhandle = open('/Users/camelia.pohoata/IdeaProjects/FlyPikachu/python-troposphere/templates/template01.json', 'w')
fhandle.write(t.to_json())
fhandle.close()