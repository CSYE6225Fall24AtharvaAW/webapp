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

variable "DB_USERNAME" {
    type = string
}
variable "DB_PASSWORD" {
    type = string
}
variable "DB_HOST" {
    type = string
}
variable "DB_PORT" {
    type = string
}
variable "DB_NAME" {
    type = string
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
  ami_name      = "webapp-ami"
  ssh_username  = "ubuntu"
  ami_users     = var.ami_users // Make the AMI private
}

// Provisioners to install requirements and application
build {
  sources = ["source.amazon-ebs.webapp"]

  provisioner "shell" {
    script = "./packer/scripts/install_dependencies.sh"
  }

  provisioner "shell" {
    script = "./packer/scripts/setup_database.sh"
  }

  provisioner "shell" {
    inline = [
        "sudo mkdir -p /home/ubuntu/webapp/app",
        "sudo chown -R ubuntu:ubuntu /home/ubuntu/webapp",
        "sudo chmod -R 755 /home/ubuntu/webapp"
    ]
  }

  provisioner "file" {
    source      = "./app/"
    destination = "/home/ubuntu/webapp/app"
  }

  provisioner "file" {
    source      = "./requirements.txt"
    destination = "/home/ubuntu/webapp/requirements.txt"
  }

  provisioner "file" {
    source      = "./packer/service/webapp.service"
    destination = "/tmp/webapp.service"
  }

  provisioner "shell" {
     environment_vars = [
      "DB_USERNAME=${var.DB_USERNAME}",
      "DB_PASSWORD=${var.DB_PASSWORD}",
      "DB_HOST=${var.DB_HOST}",
      "DB_PORT=${var.DB_PORT}",
      "DB_NAME=${var.DB_NAME}"
    ]

    script = "./packer/scripts/install_app.sh"
    execute_command = "sudo -E {{ .Vars }} bash '{{ .Path }}'"
  }

  provisioner "shell" {
    script = "./packer/scripts/setup_service.sh"
  }
}
