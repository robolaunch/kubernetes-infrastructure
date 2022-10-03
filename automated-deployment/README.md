# Automated Deployment of **robolaunch Kubernetes Infrastructure** via robolaunch-infra-deployer

**robolaunch-infra-deployer** is a python script that can provision all **robolaunch Kubernetes Infrastructure** componenets. Mainly uses **terraform** for cloud provisioning, **kubeone** for kubernetes deployment and also deploys **Kube-OVN (CNI), rook-ceph (CSI)** and **Virtual Cluster (tenancy)**.

Following step for installing prerequisities of **robolaunch-infra-deployer**. These are terraform, python3-pip, unzip, kubeone and kubectl

Pip and dependencies installation
```bash
git clone https://github.com/mkcetinkaya/robolaunch-kubernetes.git
cd robolaunch-kubernetes/automated-deployment
apt update
apt install python3-pip
pip install requirements.txt
```

Terraform installation
```bash
curl -fsSL https://apt.releases.hashicorp.com/gpg | apt-key add -
apt-add-repository "deb [arch=$(dpkg --print-architecture)] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
apt-get update -y
apt-get install terraform -y
```

Kubeone installation
```bash
apt install unzip
curl -sfL get.kubeone.io | sh
```

Kubectl installation
```bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

All variables that script needs are in the values.yaml. There are **four sections**. **Cloud** section is for cloud secret keys and region information, **Instance** section contains instance type and disk sizes, **Cluster** section for cluster name and version and finally **CNI** section for pod and service subnet details.

In order to initiate whole installation just use following command and it tooks around 15-18 minutes to deply infrastructure.

```bash
python3 robolaunch-infra-deployer.py
```
