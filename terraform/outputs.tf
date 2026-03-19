output "public_ip" {
  description = "Elastic IP address of the server"
  value       = aws_eip.scorecheck.public_ip
}

output "instance_id" {
  description = "EC2 instance ID"
  value       = var.use_spot ? aws_spot_instance_request.scorecheck[0].spot_instance_id : aws_instance.scorecheck[0].id
}

output "ssm_connect" {
  description = "AWS CLI command to open an SSM session on the server"
  value       = "aws ssm start-session --target ${var.use_spot ? aws_spot_instance_request.scorecheck[0].spot_instance_id : aws_instance.scorecheck[0].id}"
}

output "hosted_zone_id" {
  description = "Route 53 hosted zone ID"
  value       = aws_route53_zone.main.zone_id
}

output "name_servers" {
  description = "Route 53 name servers (update your domain registrar with these)"
  value       = aws_route53_zone.main.name_servers
}

output "app_url" {
  description = "Application URL"
  value       = "https://${var.domain_name}"
}
