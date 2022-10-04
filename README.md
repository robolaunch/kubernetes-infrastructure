# robolaunch Kubernetes Infrastructure

**robolaunch Kubernetes Infrastructure** is a collection of awesome open source projects and below are list of these components.

- **Containerd (CRI) -** An industry-standard container runtime
- **kube-ovn (CNI) -**  Advanced Kubernetes Network Fabric
- **Rook (CSI) -** Open-Source, Cloud-Native Storage for Kubernetes
- **Virtual Cluster -** Enabling Kubernetes Hard Multi-tenancy
- **Prometheus and Graphan a-** Monitoring infrastructure
- **ELK Stack -** Collecting, storing and analyzing Kubernetes telemetry data

Apart from above main components, 
- **kubeone -** automating cluster operations
- **terraform -** creating cloud infrastructure components are used for deploying all components.

Following steps are for deploying **robolaunch Kubernetes Infrastructure** to cloud providers. It can be deployed to both **cloud providers (AWS, Azure, GCP)** and **on-premise**. Currently supported cloud providers are **AWS** and **Hetzner Cloud** and following steps are applicable for deploying robolaunch kubernetes infrastructure to **AWS** and **Hetzner Cloud**. 

There are two ways to deploy **robolaunch Kubernetes Infrastructure", **Automated Deployment** and **Manual Deployment**. **Manual Deployment** is deploying all componenets step by step. **Automated Deployment** is using **robolaunch-infra-deployer** script.

**robolaunch-infra-deployer** is a python script and it takes only required input as a yaml file and then deploy whole infrastructure automatically.

Followings are links for each deployment methods.

- [Automated Deployment](https://github.com/mkcetinkaya/robolaunch-kubernetes/tree/main/automated-deployment)

- [Manual Deployment](https://github.com/mkcetinkaya/robolaunch-kubernetes/tree/main/manual-deployment)
