from python_terraform import *
from Crypto.PublicKey import RSA
import os
import stat
import json
import subprocess
from pathlib import Path
from kubernetes import client, config
import time
import pathlib
import yaml
import kubernetes
from pyaml_env import parse_config, BaseConfig
from loguru import logger

logger.remove()
logger.add(sys.stdout, format="[{time:HH:mm:ss}] <lvl>{message}</lvl>", level="INFO")

###Functions for creating kubernetes object from yaml -- START
def apply_simple_item(dynamic_client: kubernetes.dynamic.DynamicClient, manifest: dict, verbose: bool=False):
    api_version = manifest.get("apiVersion")
    kind = manifest.get("kind")
    resource_name = manifest.get("metadata").get("name")
    namespace = manifest.get("metadata").get("namespace")
    crd_api = dynamic_client.resources.get(api_version=api_version, kind=kind)
    try:
        crd_api.get(namespace=namespace, name=resource_name)
        crd_api.patch(body=manifest, content_type="application/merge-patch+json")
        if verbose:
            print(f"{namespace}/{resource_name} patched")
    except kubernetes.dynamic.exceptions.NotFoundError:
        crd_api.create(body=manifest, namespace=namespace)
        if verbose:
            print(f"{namespace}/{resource_name} created")

def apply_simple_item_from_yaml(dynamic_client: kubernetes.dynamic.DynamicClient, filepath: pathlib.Path, verbose: bool=False):
    with open(filepath, 'r') as f:
        manifest = yaml.safe_load(f)
        apply_simple_item(dynamic_client=dynamic_client, manifest=manifest, verbose=verbose)
###Functions for creating kubernetes object from yaml -- END

start = time.time()
user_input = BaseConfig(parse_config('values.yaml'))

cwd = os.getcwd()

###set Cloud specific environment variables -- START
if user_input.cloud.provider == "aws":
  os.environ["AWS_ACCESS_KEY_ID"] = user_input.cloud.aws_access_key_id
  os.environ["AWS_SECRET_ACCESS_KEY"] = user_input.cloud.aws_secret_access_key
  os.environ["AWS_PROFILE"] = user_input.cloud.aws_profile
elif user_input.cloud.provider == "hetzner":
  os.environ["HCLOUD_TOKEN"] = user_input.cloud.hcloud_token
###set Cloud specific environment variables -- END

###SSH private key generation -- START
key = RSA.generate(1024)
f = open("private.pem", "wb")
f.write(key.exportKey('PEM'))
f.close()
###SSH private key generation -- END

###SSH public key generation -- START
pubkey = key.publickey()
f = open("public.pub", "wb")
f.write(pubkey.exportKey('OpenSSH'))
f.close()
###SSH public key generation -- END

###Put key files to default location -- START
if user_input.cloud.provider == "aws":
  os.rename("private.pem", "terraform/aws/ssh-keys/id_rsa")
  os.chmod("terraform/aws/ssh-keys/id_rsa", stat.S_IREAD)
  os.rename("public.pub", "terraform/aws/ssh-keys/id_rsa.pub")
  private_key = Path("terraform/aws/ssh-keys/id_rsa")
  public_key = Path("terraform/aws/ssh-keys/id_rsa.pub")
elif user_input.cloud.provider == "hetzner":
  os.rename("private.pem", "terraform/hetzner/ssh-keys/id_rsa")
  os.chmod("terraform/hetzner/ssh-keys/id_rsa", stat.S_IREAD)
  os.rename("public.pub", "terraform/hetzner/ssh-keys/id_rsa.pub")
  private_key = Path("terraform/hetzner/ssh-keys/id_rsa")
  public_key = Path("terraform/hetzner/ssh-keys/id_rsa.pub")
if private_key.is_file() and public_key.is_file() :
  logger.success("SSH keys are generated and saved successfully")
else:
  logger.critical("SSH key generation failed")
###Put key files to default location -- END

time.sleep(2)

###Terraform init -- START
tfpath="terraform/" + user_input.cloud.provider
tf = Terraform(working_dir=tfpath)
tf.init(capture_output=False);
terraform_init_folder = Path(tfpath + "/.terraform/")
if terraform_init_folder.exists() :
  logger.success("Terraform initialization was successfully completed.")
else:
  logger.critical("Terraform initialization was failed")
###Terraform init -- END

time.sleep(2)

###Terraform plan -- START
if user_input.cloud.provider == "aws":
  tf.plan(capture_output=False, var={'cluster_name':user_input.cluster.name, 'aws_region': user_input.cloud.region, 'ssh_public_key_file':  cwd + "/terraform/aws/ssh-keys/id_rsa.pub", 'ssh_private_key_file':  cwd + "/terraform/aws/ssh-keys/id_rsa",
    'control_plane_type': user_input.instance.type, 'control_plane_vm_count': user_input.cluster.control_plane_vm_count, 'control_plane_volume_size': user_input.instance.root_volume_size, 'rook_volume_size': user_input.instance.rook_volume_size});
  logger.success("Terraform plan was successfully completed.")
elif user_input.cloud.provider == "hetzner":
  tf.plan(capture_output=False, var={'cluster_name':user_input.cluster.name,  'ssh_public_key_file': cwd + "/terraform/hetzner/ssh-keys/id_rsa.pub",
    'control_plane_type': user_input.instance.type,  'control_plane_replicas': user_input.cluster.control_plane_vm_count, 'rook_volume_size': user_input.instance.rook_volume_size});
  logger.success("Terraform plan was successfully completed.")
##Terraform plan -- END

###Terraform apply -- START
if user_input.cloud.provider == "aws":
  return_code, stdout, stderr = tf.apply(capture_output=False, skip_plan=True, var={'cluster_name':user_input.cluster.name, 'ssh_public_key_file':  cwd + "/terraform/aws/ssh-keys/id_rsa.pub", 'ssh_private_key_file':  cwd + "/terraform/aws/ssh-keys/id_rsa",
   'aws_region': user_input.cloud.region,'control_plane_type': user_input.instance.type, 'control_plane_vm_count': user_input.cluster.control_plane_vm_count, 'control_plane_volume_size': user_input.instance.root_volume_size,
   'rook_volume_size': user_input.instance.rook_volume_size });
  with open(tfpath + '/tf.json', 'w', encoding='utf-8') as f:
      json.dump(stdout, f, ensure_ascii=False, indent=4)
elif user_input.cloud.provider == "hetzner":
  return_code, stdout, stderr = tf.apply(capture_output=False, skip_plan=True, var={'cluster_name':user_input.cluster.name, 'ssh_public_key_file': cwd + "/terraform/hetzner/ssh-keys/id_rsa.pub",
   'control_plane_type': user_input.instance.type, 'control_plane_replicas': user_input.cluster.control_plane_vm_count, 'rook_volume_size': user_input.instance.rook_volume_size });
  with open(tfpath + '/tf.json', 'w', encoding='utf-8') as f:
      json.dump(stdout, f, ensure_ascii=False, indent=4)

tfstate=tfpath + '/terraform.tfstate'
if user_input.cloud.provider == "aws":
  if user_input.cluster.name + "-cp-1" in open(tfstate).read():
    logger.success("Terraform applied successfully and cloud infrastructure is ready for kubernetes deployment")
  else:
    logger.critical("Terraform apply process was failed")
elif user_input.cloud.provider == "hetzner":
  if user_input.cluster.name + "-control-plane-1" in open(tfstate).read():
    logger.success("Terraform applied successfully and cloud infrastructure is ready for kubernetes deployment")
  else:
    logger.critical("Terraform apply process was failed")
###Terraform apply -- END

time.sleep(2)

###Kubernetes deployment with kubeone -- START
##ssh-add do not run successfully as others linux command. So below code block set relevant env variable before ssh-add command.
with open('kubeone/config.yaml','r') as file:
    filedata = file.read()
    filedata = filedata.replace('<provider>',user_input.cloud.provider)
    filedata = filedata.replace('<kubernetes_version>',user_input.cluster.kubernetes_version)
with open('kubeone/config-edited.yaml','w') as file:
    file.write(filedata)

tfjson = Path(tfpath + "/tf.json")
if tfjson.is_file():
  p = subprocess.Popen('ssh-agent -s', stdin = subprocess.PIPE, stdout =
  subprocess.PIPE, stderr = subprocess.PIPE, shell = True,
  universal_newlines = True)
  outinfo, errinfo = p.communicate()
  lines = outinfo.split('\n')
  for line in lines[:-1]:
    left, right = line.split(';', 1)
    if '=' in left:
      varname, varvalue = left.split('=', 1)
      os.environ[varname] = varvalue
  logger.info("Kubernetes deployment is in progress and it takes aroud 6-9 minutes to be completed")
  time.sleep(2)
  kubeone_command="ssh-agent && ssh-add " + cwd + "/terraform/" + user_input.cloud.provider +"/ssh-keys/id_rsa" + "  && sleep 3 && kubeone apply --manifest kubeone/config-edited.yaml --auto-approve --tfjson " + tfpath
  os.system(kubeone_command)
###Kubernetes deployment with kubeone -- END

###Kubernetes Clients initializations -- START
kubeconfig=user_input.cluster.name + "-kubeconfig"
config.load_kube_config(kubeconfig)
v1 = client.CoreV1Api()

kubernetes.config.load_kube_config(kubeconfig)
DYNAMIC_CLIENT = kubernetes.dynamic.DynamicClient(
    kubernetes.client.api_client.ApiClient()
)
###Kubernetes Clients initializations -- END

ret_kubernetes = v1.list_namespaced_pod("kube-system")
for i in ret_kubernetes.items:
  if "machine-controller" in i.metadata.name and i.status.phase == "Running":
    logger.success("Kubernetes deployment completed successfully")
    break

time.sleep(2)

###Delete unused kubeone addons -- START
apps_v1 = client.AppsV1Api()
if user_input.cloud.provider == "aws":
  ret_trial=apps_v1.delete_namespaced_daemon_set(namespace="kube-system",name="canal")
  ret_trial=apps_v1.delete_namespaced_daemon_set(namespace="kube-system",name="ebs-csi-node")
  ret_trial=apps_v1.delete_namespaced_deployment(namespace="kube-system",name="calico-kube-controllers")
  ret_trial=apps_v1.delete_namespaced_deployment(namespace="kube-system",name="ebs-csi-controller")
  ret_trial=apps_v1.delete_namespaced_deployment(namespace="kube-system",name="snapshot-controller")
elif user_input.cloud.provider == "hetzner":
  ret_trial=apps_v1.delete_namespaced_daemon_set(namespace="kube-system",name="canal")
  ret_trial=apps_v1.delete_namespaced_daemon_set(namespace="kube-system",name="hcloud-csi-node")
  ret_trial=apps_v1.delete_namespaced_stateful_set(namespace="kube-system",name="hcloud-csi-controller")
  ret_trial=apps_v1.delete_namespaced_deployment(namespace="kube-system",name="calico-kube-controllers")
###Delete unused kubeone addons -- END

###Kube-ovn CNI Installation -- START
with open('kube-ovn/kube-ovn.sh','r') as file:
    filedata = file.read()
    filedata = filedata.replace('<pod_cidr>',user_input.cni.pod_cidr)
    filedata = filedata.replace('<pod_gateway>',user_input.cni.pod_gateway)
    filedata = filedata.replace('<service_cidr>',user_input.cni.service_cidr)
with open('kube-ovn/kube-ovn-edited.sh','w') as file:
    file.write(filedata)

os.system("export KUBECONFIG=" + kubeconfig + " && bash kube-ovn/kube-ovn-edited.sh")
ret_kubeovn = v1.list_namespaced_pod("kube-system")
for i in ret_kubeovn.items:
  if "kube-ovn-controller" in i.metadata.name and i.status.phase == "Running":
    logger.success("Kube-ovn CNI installation completed")
    break
###Kube-ovn CNI Installation -- END

time.sleep(2)

###Untaint master nodes for deploying rook-ceph and other system components also label master nodes with supercluster label -- START
config.load_kube_config(kubeconfig)
v1 = client.CoreV1Api()
ret = v1.list_node()
for i in ret.items:
  cmd_taint="export KUBECONFIG=" + kubeconfig + " && " + "kubectl taint nodes " + i.metadata.name + " node-role.kubernetes.io/master-"
  os.system(cmd_taint)
  cmd_label="export KUBECONFIG=" + kubeconfig + " && " + "kubectl label node " + i.metadata.name + " super-cluster=" + user_input.cloud.provider + "-" + user_input.cloud.region
  os.system(cmd_label)
logger.success("All master nodes are untainted")
###Untaint master nodes for deploying rook-ceph and other system components also label master nodes with supercluster label -- END

###Redeploy node-local-dns in order to prevent port overlapping with Virtual Cluster components -- START
apply_simple_item_from_yaml(DYNAMIC_CLIENT, "node-local-dns/nodelocaldns-cm.yaml", verbose=True)
apply_simple_item_from_yaml(DYNAMIC_CLIENT, "node-local-dns/nodelocaldns-daemonset.yaml", verbose=True)
logger.success("Node local dns is patched in order to prevent port overlapping with Virtual Cluster")
###Redeploy node-local-dns in order to prevent port overlapping with Virtual Cluster components -- END

###Deploy Virtualcluster componenents --- START
apply_simple_item_from_yaml(DYNAMIC_CLIENT, "vc/tenancy.x-k8s.io_virtualclusters.yaml", verbose=True)
apply_simple_item_from_yaml(DYNAMIC_CLIENT, "vc/tenancy.x-k8s.io_clusterversions.yaml", verbose=True)

for filename in os.listdir("vc/"):
    with open("vc/" + filename, "r") as f:
        buff = []
        i = 1
        for line in f:
            if line.startswith('#'):
                continue  # skip comments
            if line.strip() and line.strip() != "---":  #skips the empty lines
              buff.append(line)
            if line.strip() == "---":
              file="vc/" + filename.replace('.yaml','') + "_" + str(i) + ".yaml"
              output = open(file ,'w')
              output.write(''.join(buff))
              output.close()
              apply_simple_item_from_yaml(DYNAMIC_CLIENT, file, verbose=True)
              os.remove(file)
              i+=1
              buff = [] #buffer reset

flag="false"
while True:
  ret = v1.list_namespaced_pod("vc-manager")
  for i in ret.items:
    if i.status.phase == "Running" and "vc-manager-" in i.metadata.name:
      flag="true"
      logger.success("Virtual Cluster components was deployed successfully")
      break
    else:
      flag="false"
  if flag=="true":
    break
  else:
    continue
###Deploy Virtualcluster componenents --- END

time.sleep(2)

###Rook-Ceph deployment -- a) CRDS, Operators and Roles etc-- -- START
for filename in os.listdir("rook/common/"):
    with open("rook/common/" + filename, "r") as f:
        buff = []
        i = 1
        for line in f:
            if line.startswith('#'):
                continue  # skip comments
            if line.strip() and line.strip() != "---":  #skips the empty lines
              buff.append(line)
            if line.strip() == "---":
              file="rook/common/" + filename.replace('.yaml','') + "_" + str(i) + ".yaml"
              output = open(file ,'w')
              output.write(''.join(buff))
              output.close()
              apply_simple_item_from_yaml(DYNAMIC_CLIENT, file, verbose=True)
              os.remove(file)
              i+=1
              buff = [] #buffer reset

###Rook-Ceph deployment -- b) Main Ceph components--
if user_input.cloud.provider == "aws":
  if user_input.cluster.control_plane_vm_count == 3:
    cluster_file="rook/aws/cluster-three-nodes.yaml"
  elif user_input.cluster.control_plane_vm_count == 1:
    cluster_file="rook/aws/cluster-one-node.yaml"
  with open(cluster_file, 'r') as file :
    filedata = file.read()
elif user_input.cloud.provider == "hetzner":
  if user_input.cluster.control_plane_vm_count == 3:
    cluster_file="rook/hetzner/cluster-three-nodes.yaml"
  elif user_input.cluster.control_plane_vm_count == 1:
    cluster_file="rook/hetzner/cluster-one-node.yaml"
  with open(cluster_file, 'r') as file :
    filedata = file.read()

flag= False
while True:
  ret = v1.list_namespaced_pod("rook-ceph")
  for i in ret.items:
    if i.status.phase == "Running" and "rook-ceph-operator" in i.metadata.name:
      ret_node = v1.list_node()
      j=1
      for k in ret_node.items:
        text="control-plane-0"+ str(j)
        filedata = filedata.replace(text, k.metadata.name)
        j+=1
        flag= True
  if flag is True:
    break
  else:
    continue
  break
with open('rook/cluster-edited.yaml', 'w') as file:
  file.write(filedata)


logger.info("Ceph cluster deployment is in progress and it takes aroud 5 minutes to be completed")
apply_simple_item_from_yaml(DYNAMIC_CLIENT, "rook/cluster-edited.yaml", verbose=True)

###Rook-Ceph deployment -- c) StorageClass Deployment--
flag="false"
while True:
  ret = v1.list_namespaced_pod("rook-ceph")
  for i in ret.items:
    if i.status.phase == "Running" and "rook-ceph-osd" in i.metadata.name:
      logger.success("Ceph cluster was deployed successfully")
      if user_input.cluster.control_plane_vm_count == 3:
        apply_simple_item_from_yaml(DYNAMIC_CLIENT, "rook/sc/three-nodes/ceph-block-pool-metadata.yaml", verbose=True)
        apply_simple_item_from_yaml(DYNAMIC_CLIENT, "rook/sc/three-nodes/ceph-block-pool-data.yaml", verbose=True)
        apply_simple_item_from_yaml(DYNAMIC_CLIENT, "rook/sc/three-nodes/storage-class.yaml", verbose=True)
      elif user_input.cluster.control_plane_vm_count == 1:
        apply_simple_item_from_yaml(DYNAMIC_CLIENT, "rook/sc/one-node/ceph-block-pool-data.yaml", verbose=True)
        apply_simple_item_from_yaml(DYNAMIC_CLIENT, "rook/sc/one-node/storage-class.yaml", verbose=True)
      flag="true"
      break
    else:
      flag="false"
  if flag=="true":
    break
  else:
    continue

logger.success("Storage class was sucessfully deployed")
###Rook-Ceph deployment for -- END

###Ingress-Nginx deployment -- Start
logger.info("Ingress Nginx deployment is in progress and it takes aroud 1 minutes to be completed")
time.sleep(2)
helm_ingress_command="export KUBECONFIG=" + kubeconfig + " && " + "helm upgrade --install ingress-nginx ingress-nginx --repo https://kubernetes.github.io/ingress-nginx --namespace ingress-nginx --create-namespace -f ingress/values.yaml "
os.system(helm_ingress_command)
time.sleep(2)
###Ingress-Nginx deployment -- End

###Internal Ingress-Nginx deployment -- Start
logger.info("Internal Ingress Nginx deployment is in progress and it takes aroud 1 minutes to be completed")
time.sleep(2)
helm_internal_ingress_command="export KUBECONFIG=" + kubeconfig + " && " + "helm upgrade --install internal-ingress-nginx ingress-nginx --repo https://kubernetes.github.io/ingress-nginx --namespace internal-ingress-nginx --create-namespace -f internal-ingress/values.yaml "
os.system(helm_internal_ingress_command)
time.sleep(2)
###Internal Ingress-Nginx deployment -- End

###Kubernetes dashboard Deployment -- Start
for filename in os.listdir("dashboard/"):
    with open("dashboard/" + filename, "r") as f:
        buff = []
        i = 1
        for line in f:
            if line.startswith('#'):
                continue  # skip comments
            if line.strip() and line.strip() != "---":  #skips the empty lines
              buff.append(line)
            if line.strip() == "---":
              file="dashboard/" + filename.replace('.yaml','') + "_" + str(i) + ".yaml"
              output = open(file ,'w')
              output.write(''.join(buff))
              output.close()
              apply_simple_item_from_yaml(DYNAMIC_CLIENT, file, verbose=True)
              os.remove(file)
              i+=1
              buff = [] #buffer reset
###Kubernetes dashboard Deployment -- End

###Nvidia device plugin daemonset deployment in AWS -- START
if user_input.cloud.provider == "aws":
  apply_simple_item_from_yaml(DYNAMIC_CLIENT, "nvidia/nvidia-device-plugin-ds.yaml", verbose=True)
  logger.success("Deployed nvidia device plugin daemonset")
###Nvidia device plugin daemonset deployment in AWS -- STOP

###Machine Deployment File Generation -- Start
if user_input.cloud.provider == "aws":
  f = open ('terraform/aws/terraform.tfstate', "r")
  data = json.loads(f.read())
  with open('kubeone/aws/machine-deployment.yaml', 'r') as file :
    filedata = file.read()
  for i in data['resources']:
      if i['type'] == "aws_key_pair":
        filedata = filedata.replace("<ssh-key>", i['instances'][0]['attributes']['public_key'])
      elif i['type'] == "aws_vpc":
        filedata = filedata.replace("<vpc-id>", i['instances'][0]['attributes']['id'])
      elif i['type'] == "aws_subnet":
        filedata = filedata.replace("<subnet-id>", i['instances'][0]['attributes']['id'])
      elif i['type'] == "aws_instance" and i['name'] == "control_plane":
        filedata = filedata.replace("<ami-id>", i['instances'][0]['attributes']['ami'])
      elif i['type'] == "aws_security_group" and i['name'] == "common":
        security_group_common=i['instances'][0]['attributes']['id']
      elif i['type'] == "aws_security_group" and i['name'] == "worker-sg":
        security_group_worker=i['instances'][0]['attributes']['id']
# Closing file
  f.close()

  filedata = filedata.replace("<region>", user_input.cloud.region)
  filedata = filedata.replace("<availability-zone>", user_input.cloud.region + "a")
  filedata = filedata.replace("<instance-type>", user_input.instance.type)
  filedata = filedata.replace("<instance-profile>", user_input.cluster.name + "-host")
  filedata = filedata.replace("<kubernetes-version>", user_input.cluster.kubernetes_version)
  filedata = filedata.replace("<kubernetes-cluster-tag>", user_input.cluster.name)
  filedata = filedata.replace("<security-group-1>", security_group_common)
  filedata = filedata.replace("<security-group-2>", security_group_worker)

  with open('kubeone/aws/machine-deployment-buffer-without-gpu.yaml', 'w') as file:
    file.write(filedata)
  ###Machine Deployment File Generation -- End
elif user_input.cloud.provider == "hetzner":
  f = open ('terraform/hetzner/terraform.tfstate', "r")
  data = json.loads(f.read())
  with open('kubeone/hetzner/machine-deployment.yaml', 'r') as file :
    filedata = file.read()
  for i in data['resources']:
      if i['type'] == "hcloud_ssh_key":
        filedata = filedata.replace("<ssh-key>", i['instances'][0]['attributes']['public_key'])
      elif i['type'] == "hcloud_network":
        filedata = filedata.replace("<network-id>", i['instances'][0]['attributes']['id'])
      elif i['type'] == "hcloud_firewall":
        filedata = filedata.replace("<firewall-id>", i['instances'][0]['attributes']['id'])
      elif i['type'] == "hcloud_server":
        filedata = filedata.replace("<datacenter-id>", i['instances'][0]['attributes']['datacenter'])
# Closing file
  f.close()

  filedata = filedata.replace("<instance-type>", user_input.instance.type)
  filedata = filedata.replace("<kubernetes-version>", user_input.cluster.kubernetes_version)

  with open('kubeone/hetzner/machine-deployment-buffer-without-gpu.yaml', 'w') as file:
    file.write(filedata)
  ###Machine Deployment File Generation -- End

###Machine Deployment File Generation for GPU instances-- Start
if user_input.cloud.provider == "aws":
  f = open ('terraform/aws/terraform.tfstate', "r")
  data = json.loads(f.read())
  with open('kubeone/aws/machine-deployment-gpu.yaml', 'r') as file :
    filedata_gpu = file.read()
  for i in data['resources']:
      if i['type'] == "aws_key_pair":
        filedata_gpu = filedata_gpu.replace("<ssh-key>", i['instances'][0]['attributes']['public_key'])
      elif i['type'] == "aws_vpc":
        filedata_gpu = filedata_gpu.replace("<vpc-id>", i['instances'][0]['attributes']['id'])
      elif i['type'] == "aws_subnet":
        filedata_gpu = filedata_gpu.replace("<subnet-id>", i['instances'][0]['attributes']['id'])
      elif i['type'] == "aws_security_group" and i['name'] == "common":
        security_group_common=i['instances'][0]['attributes']['id']
      elif i['type'] == "aws_security_group" and i['name'] == "worker-sg":
        security_group_worker=i['instances'][0]['attributes']['id']
# Closing file
  f.close()

  filedata_gpu = filedata_gpu.replace("<region>", user_input.cloud.region)
  filedata_gpu = filedata_gpu.replace("<availability-zone>", user_input.cloud.region + "a")
  filedata_gpu = filedata_gpu.replace("<instance-type>", user_input.gpu_worker.type)
  filedata_gpu = filedata_gpu.replace("<instance-profile>", user_input.cluster.name + "-host")
  filedata_gpu = filedata_gpu.replace("<kubernetes-version>", user_input.cluster.kubernetes_version)
  filedata_gpu = filedata_gpu.replace("<kubernetes-cluster-tag>", user_input.cluster.name)
  filedata_gpu = filedata_gpu.replace("<security-group-1>", security_group_common)
  filedata_gpu = filedata_gpu.replace("<security-group-2>", security_group_worker)
  filedata_gpu = filedata_gpu.replace("<ami-id>", user_input.gpu_worker.ami_id)

  with open('kubeone/aws/machine-deployment-buffer-gpu.yaml', 'w') as file:
    file.write(filedata_gpu)
  ###Machine Deployment File Generation for GPU instances-- End

###Deploy internal OperatingSystemProvider for Ubuntu in order to overcome node issue in hetzner -- START
if user_input.cloud.provider == "hetzner":
  apply_simple_item_from_yaml(DYNAMIC_CLIENT, "kubeone/hetzner/custom_addons/osp-ubuntu-internal.yaml", verbose=True)
  logger.success("Deployed internal OperatingSystemProvider for Ubuntu in order to overcome node issue in hetzner")
###Deploy internal OperatingSystemProvider for Ubuntu in order to overcome node issue in hetzner -- START

###Deploy internal OperatingSystemProvider for Ubuntu in order to overcome gpu node issue in AWS -- START
if user_input.cloud.provider == "aws":
  apply_simple_item_from_yaml(DYNAMIC_CLIENT, "kubeone/aws/custom_addons/osp-ubuntu-aws-gpu.yaml", verbose=True)
  logger.success("Deployed internal OperatingSystemProvider for Ubuntu in order to overcome gpu node issue in AWS")
###Deploy internal OperatingSystemProvider for Ubuntu in order to overcome node issue in hetzner -- STOP


end = time.time()
elapsed_time=end-start
logger.success("Completed all steps in a " + str(int(elapsed_time)) + " seconds.")  