region = "us-east-1"
cluster_name = "scorecheck-eks"
vpc_cidr = "10.0.0.0/16"
subnet_cidrs = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
node_group_instance_type = "t3.medium"
node_group_desired_capacity = 2
domain_name = "scorecheck.ca"