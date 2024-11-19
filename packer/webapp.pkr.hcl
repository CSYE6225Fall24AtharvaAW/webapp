variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "source_ami" {
  type    = string
  default = "ami-0866a3c8686eaeeba" //the latest Ubuntu 24.04 LTS AMI ID
}

variable "instance_type" {
  type    = string
  default = "t2.small"
}

variable "aws_profile" {
  type = string
}

variable "ami_users" {
  type = list(string)
}

packer {
  required_plugins {
    amazon = {
      version = ">= 1.0.0"
      source  = "github.com/hashicorp/amazon"
    }
  }
}

// Configure AWS Builder using a profile
source "amazon-ebs" "webapp" {
  profile       = var.aws_profile
  region        = var.aws_region
  source_ami    = var.source_ami
  instance_type = var.instance_type
  ami_name      = "webapp-ami-{{timestamp}}"
  ssh_username  = "ubuntu"
  ami_users     = var.ami_users
}

// Provisioners to install requirements and application
build {
  sources = ["source.amazon-ebs.webapp"]

  provisioner "shell" {
    script = "./packer/scripts/install_dependencies.sh"
  }

  // Removing the database setup from the EC2 image
  // No longer provisioning the setup_database.sh script

  // Create user and set permissions
  provisioner "shell" {
    inline = [
      "sudo groupadd -f csye6225",
      "sudo useradd -g csye6225 -M -s /usr/sbin/nologin csye6225",
      "sudo mkdir -p /home/csye6225/webapp/app",
      "sudo chown -R ubuntu:csye6225 /home/csye6225/webapp", // Allow Packer to upload files
      "sudo chmod -R 775 /home/csye6225/webapp"              // Ensure write permissions for the group
    ]
  }

  // Copy the web app and other files
  provisioner "file" {
    source      = "./app/"
    destination = "/home/csye6225/webapp/app"
  }

  provisioner "file" {
    source      = "./requirements.txt"
    destination = "/home/csye6225/webapp/requirements.txt"
  }

  provisioner "file" {
    source      = "./packer/service/webapp.service"
    destination = "/tmp/webapp.service"
  }

  // Install app with environment variables passed as user data
  provisioner "shell" {
    script          = "./packer/scripts/install_app.sh"
    execute_command = "sudo -E {{ .Vars }} bash '{{ .Path }}'"
  }

  provisioner "shell" {
    script = "./packer/scripts/setup_service.sh"
  }

  // Install and configure CloudWatch Agent
  provisioner "shell" {
    inline = [
      "sudo mkdir -p /opt/aws/amazon-cloudwatch-agent/etc",
      "sudo chown -R ubuntu:ubuntu /opt/aws/amazon-cloudwatch-agent"
    ]
  }

  provisioner "file" {
    source      = "./cloudwatch-config.json"
    destination = "/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json"
  }


  provisioner "shell" {
    inline = [
      "wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb",
      "sudo dpkg -i ./amazon-cloudwatch-agent.deb",
      "sudo systemctl enable amazon-cloudwatch-agent",
      "sudo systemctl start amazon-cloudwatch-agent"
    ]
  }

  provisioner "shell" {
    inline = [
      "sudo mkdir -p /home/csye6225/webapp/app",
      "sudo chown -R csye6225:csye6225 /home/csye6225/webapp",
      "sudo chmod -R 775 /home/csye6225/webapp/app"
    ]
  }
}
