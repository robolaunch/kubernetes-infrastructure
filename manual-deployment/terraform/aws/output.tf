/*
Copyright 2019 The KubeOne Authors.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
*/

output "kubeone_api" {
  description = "kube-apiserver LB endpoint"

  value = {
    endpoint                    = local.kubeapi_endpoint
    apiserver_alternative_names = var.apiserver_alternative_names
  }
}

output "ssh_commands" {
  value = formatlist("ssh -J ${local.bastion_user}@${aws_instance.bastion.public_ip} ${local.ssh_username}@%s", aws_instance.control_plane.*.private_ip)
}

output "kubeone_hosts" {
  description = "Control plane endpoints to SSH to"

  value = {
    control_plane = {
      cluster_name         = var.cluster_name
      cloud_provider       = "aws"
      private_address      = aws_instance.control_plane.*.private_ip
      hostnames            = aws_instance.control_plane.*.private_dns
      operating_system     = var.os
      ssh_agent_socket     = var.ssh_agent_socket
      ssh_port             = var.ssh_port
      ssh_private_key_file = var.ssh_private_key_file
      ssh_user             = local.ssh_username
      bastion              = aws_instance.bastion.public_ip
      bastion_port         = var.bastion_port
      bastion_user         = local.bastion_user
      labels               = var.control_plane_labels
      # uncomment to following to set those kubelet parameters. More into at:
      # https://kubernetes.io/docs/tasks/administer-cluster/reserve-compute-resources/
      # kubelet            = {
      #   system_reserved = "cpu=200m,memory=200Mi"
      #   kube_reserved   = "cpu=200m,memory=300Mi"
      #   eviction_hard   = ""
      #   max_pods        = 110
      # }
    }
  }
}
