# Step by Step Manual Deployment of **robolaunch Kubernetes Infrastructure**

Cureently supported cloud providers are **AWS** and **Hetzner Cloud**. Following steps are based on these and other cloud providers(Azure, GCP) deployment guide will be added. 

Installation of prerequisities like terraform, kubeon, kubectl..
```bash
apt update
curl -fsSL https://apt.releases.hashicorp.com/gpg | apt-key add -
apt-add-repository "deb [arch=$(dpkg --print-architecture)] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
apt-get update -y
apt-get install terraform -y
apt install unzip
curl -sfL get.kubeone.io | sh
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

Create SSH key that will be used for kubernetes nodes. 
```bash
ssh-keygen # key file must be remain in default location /root/.ssh/id_rsa. And paraphrases can be empty
```
Clone repository and change directory to manual-deployment
```bash
git clone https://github.com/mkcetinkaya/robolaunch-kubernetes.git
cd robolaunch-kubernetes/manual-deployment
```
## **Cloud Providers Specific Steps**

### **1- For AWS Deployment:**

Create an AWS user with permission **ec2** and **IAM** full access from aws web console. Set AWS specific env variable for terraform operations via changing your key values.
```bash
export AWS_ACCESS_KEY_ID=AWS-ACCESS-KEY
export AWS_SECRET_ACCESS_KEY=AWS-SECRET-ACCESS-KEY
export AWS_PROFILE="default"
```
Currently AWS specific variables are **t3a.xlarge** for **control-plane image type** and **us-east-2* for **aws region**. Follow below steps for infrastructure provisioning via terraform. Terraform will provision VPC, subnet, security-group, load balancer, instance and volume. Main output will be **three master nodes** for **kubernetes Control Plane** and **one node as a jumphost**. 

terraform steps: give cluster name whan asked **dev-cluster** or something that would like to set your cluster name.

```bash
cd terraform/aws
terraform init
terraform plan
terraform apply
terraform output -json > tf.json
cd ../../
```

In order to kubeone to connect instances via ssh for deploying kubernetes componenets, following commands start ssh agent and set existing ssh key.
```bash
eval `ssh-agent -s`
ssh-add /root/.ssh/id_rsa
```
Create config.yaml and deploy infra with kubeone. Config file defines kubernetes version and current version is 1.23.9, you can change to provision any version of kubernetes. It tooks around 6-9 minutes.
```bash
kubeone install --manifest kubeone/aws/config.yaml --tfjson terraform/aws/
```
When kubeone step finishes, you can remove unused componenets. We will use kube-ovn as CNI and rook-ceph as CSI, so we will remove existing CNI and CSI.
```bash
export KUBECONFIG=dev-test-kubeconfig
kubectl delete daemonset canal ebs-csi-node -n kube-system
kubectl delete deployment calico-kube-controllers ebs-csi-controller snapshot-controller -n kube-system
```

Next step is installing kube-ovn componenets, currently network configuration is as follows. You can change in kube-ovn.sh script with desired values.
```bash
POD_CIDR="10.200.0.0/16"                # Do NOT overlap with NODE/SVC/JOIN CIDR
POD_GATEWAY="10.200.0.1"
SVC_CIDR="10.201.0.0/16"                # Do NOT overlap with NODE/POD/JOIN CIDR
```
```bash
bash kube-ovn/kube-ovn.sh
```

Local DNS are being used in our platform for caching DNS records host level. Following commands will change local dns port from **8080** to **8090**, in order to prevent  port overlapping with virtualcluster.
```bash
kubectl apply -f node-local-dns/nodelocaldns-cm.yaml
kubectl apply -f node-local-dns/nodelocaldns-daemonset.yaml
```

Untaint three masters for rook deployment to master nodes. Change nodename wit the actual ones.
```bash
kubectl taint nodes <master-node-1> node-role.kubernetes.io/master-
kubectl taint nodes <master-node-2> node-role.kubernetes.io/master-
kubectl taint nodes <master-node-3> node-role.kubernetes.io/master-
```

Following step is for deploying virtual cluster. Virtual cluster is used for kubernetes multitenancy and we will be deploying new(child) kubernetes clusters on existing cluster(super)
```bash
kubectl create -f vc/tenancy.x-k8s.io_clusterversions.yaml
kubectl create -f vc/tenancy.x-k8s.io_virtualclusters.yaml
kubectl create -f vc/all-in-one.yaml
```

Rook-Ceph deployment for CSI provisioning.
Deploy operator, crds, and common objects like clusterrole etc
```bash
kubectl create -f rook/crds.yaml -f rook/common.yaml -f rook/operator.yaml
```

deploy ceph cluster, only changes nodenames in rook/cluster.yaml file currently nodemaes are dev-k8s-m01/02/m03. It tooks around 5 minutes and wait three rook-osd-xxx pod is in running state. You can check with "watch kubectl get pods -n rook-ceph"
```bash
kubectl create -f rook/aws/cluster.yaml
```

Deploy toolbox for checking deployment is successful. Ceph status and Cepk OSD status must be ok.
```bash
kubectl create -f rook/toolbox.yaml
kubectl exec -it rook-ceph-tools-xxx  -n rook-ceph -- bash
ceph status
ceph osd status
```

Deploy rbd block storageclass and make it default storage class.
```bash
kubectl create -f rook/storageclass-ec.yaml
kubectl patch storageclass rook-ceph-block -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```
## 2- For Hetzner Cloud Deployment

Generate an API Token with **Read and Write** access by using Hetzner Cloud Console and set env variable for terraform operations via changing your token value.
```bash
export HCLOUD_TOKEN=Hetzner-Cloud-Token
```
Currently Hetzner Specific specific terraform variables are **cpx31** for **control-plane image type**. Follow below steps for infrastructure provisioning via terraform. Terraform will provision  subnet, security-rules, load balancer, instance and volume. Main output will be **three master nodes** for **kubernetes Control Plane**. 

terraform steps: give cluster name whan asked **dev-cluster** or something that would like to set your cluster name.

```bash
cd terraform/hetzner
terraform init
terraform plan
terraform apply
terraform output -json > tf.json
cd ../../
```

In order to kubeone to connect instances via ssh for deploying kubernetes componenets, following commands start ssh agent and set existing ssh key.
```bash
eval `ssh-agent -s`
ssh-add /root/.ssh/id_rsa
```
Create config.yaml and deploy infra with kubeone. Config file defines kubernetes version and current version is 1.23.9, you can change to provision any version of kubernetes. It tooks around 6-9 minutes.
```bash
kubeone install --manifest kubeone/hetzner/config.yaml --tfjson terraform/hetzner/
```
When kubeone step finishes, you can remove unused componenets. We will use kube-ovn as CNI and rook-ceph as CSI, so we will remove existing CNI and CSI.
```bash
export KUBECONFIG=dev-test-kubeconfig
kubectl delete statefulset hcloud-csi-controller -n kube-system
kubectl delete daemonset canal hcloud-csi-node -n kube-syste
kubectl delete deployment calico-kube-controllers -n kube-system
```

Next step is installing kube-ovn componenets, currently network configuration is as follows. You can change in kube-ovn.sh script with desired values.
```bash
POD_CIDR="10.200.0.0/16"                # Do NOT overlap with NODE/SVC/JOIN CIDR
POD_GATEWAY="10.200.0.1"
SVC_CIDR="10.201.0.0/16"                # Do NOT overlap with NODE/POD/JOIN CIDR
```
```bash
bash kube-ovn/kube-ovn.sh
```

Local DNS are being used in our platform for caching DNS records host level. Following commands will change local dns port from **8080** to **8090**, in order to prevent  port overlapping with virtualcluster.
```bash
kubectl apply -f node-local-dns/nodelocaldns-cm.yaml
kubectl apply -f node-local-dns/nodelocaldns-daemonset.yaml
```

Untaint three masters for rook deployment to master nodes. Change nodename wit the actual ones.
```bash
kubectl taint nodes <master-node-1> node-role.kubernetes.io/master-
kubectl taint nodes <master-node-2> node-role.kubernetes.io/master-
kubectl taint nodes <master-node-3> node-role.kubernetes.io/master-
```

Following step is for deploying virtual cluster. Virtual cluster is used for kubernetes multitenancy and we will be deploying new(child) kubernetes clusters on existing cluster(super)
```bash
kubectl create -f vc/tenancy.x-k8s.io_clusterversions.yaml
kubectl create -f vc/tenancy.x-k8s.io_virtualclusters.yaml
kubectl create -f vc/all-in-one.yaml
```

Rook-Ceph deployment for CSI provisioning.
Deploy operator, crds, and common objects like clusterrole etc
```bash
kubectl create -f rook/crds.yaml -f rook/common.yaml -f rook/operator.yaml
```

deploy ceph cluster, only changes nodenames in rook/cluster.yaml file currently nodemaes are dev-k8s-m01/02/m03. It tooks around 5 minutes and wait three rook-osd-xxx pod is in running state. You can check with "watch kubectl get pods -n rook-ceph"
```bash
kubectl create -f rook/hetzner/cluster.yaml
```

Deploy toolbox for checking deployment is successful. Ceph status and Cepk OSD status must be ok.
```bash
kubectl create -f rook/toolbox.yaml
kubectl exec -it rook-ceph-tools-xxx  -n rook-ceph -- bash
ceph status
ceph osd status
```

Deploy rbd block storageclass and make it default storage class.
```bash
kubectl create -f rook/storageclass-ec.yaml
kubectl patch storageclass rook-ceph-block -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

