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

###set AWS specific environment variables -- START
if user_input.cloud.provider == "aws":
  os.environ["AWS_ACCESS_KEY_ID"] = user_input.cloud.aws_access_key_id
  os.environ["AWS_SECRET_ACCESS_KEY"] = user_input.cloud.aws_secret_access_key
  os.environ["AWS_PROFILE"] = user_input.cloud.aws_profile
elif user_input.cloud.provider == "hetzner":
  os.environ["HCLOUD_TOKEN"] = user_input.cloud.hcloud_token
###set AWS specific environment variables -- END

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
os.rename("private.pem", "/root/.ssh/id_rsa")
os.chmod("/root/.ssh/id_rsa", stat.S_IREAD)
os.rename("public.pub", "/root/.ssh/id_rsa.pub")
private_key = Path("/root/.ssh/id_rsa")
public_key = Path("/root/.ssh/id_rsa.pub")
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
  tf.plan(capture_output=False, var={'cluster_name':user_input.cluster.name, 'aws_region': user_input.cloud.region, 
    'control_plane_type': user_input.instance.type, 'control_plane_volume_size': user_input.instance.root_volume_size, 'rook_volume_size': user_input.instance.rook_volume_size});
  logger.success("Terraform plan was successfully completed.")
elif user_input.cloud.provider == "hetzner":
  tf.plan(capture_output=False, var={'cluster_name':user_input.cluster.name,  
    'control_plane_type': user_input.instance.type,  'rook_volume_size': user_input.instance.rook_volume_size});
  logger.success("Terraform plan was successfully completed.")  
##Terraform plan -- END

###Terraform apply -- START
if user_input.cloud.provider == "aws":
  return_code, stdout, stderr = tf.apply(capture_output=False, skip_plan=True, var={'cluster_name':user_input.cluster.name,
   'aws_region': user_input.cloud.region,'control_plane_type': user_input.instance.type, 'control_plane_volume_size': user_input.instance.root_volume_size, 
   'rook_volume_size': user_input.instance.rook_volume_size });
  with open(tfpath + '/tf.json', 'w', encoding='utf-8') as f:
      json.dump(stdout, f, ensure_ascii=False, indent=4)
elif user_input.cloud.provider == "hetzner":
  return_code, stdout, stderr = tf.apply(capture_output=False, skip_plan=True, var={'cluster_name':user_input.cluster.name,
   'control_plane_type': user_input.instance.type, 'rook_volume_size': user_input.instance.rook_volume_size });
  with open(tfpath + '/tf.json', 'w', encoding='utf-8') as f:
      json.dump(stdout, f, ensure_ascii=False, indent=4)

tfstate=tfpath + '/terraform.tfstate'
if user_input.cloud.provider == "aws":
  if user_input.cluster.name + "-cp-1" in open(tfstate).read() and user_input.cluster.name + "-cp-2" in open(tfstate).read() and user_input.cluster.name + "-cp-3" in open(tfstate).read():
    logger.success("Terraform applied successfully and cloud infrastructure is ready for kubernetes deployment")
  else:
    logger.critical("Terraform apply process was failed")
elif user_input.cloud.provider == "hetzner":
  if user_input.cluster.name + "-control-plane-1" in open(tfstate).read() and user_input.cluster.name + "-control-plane-2" in open(tfstate).read() and user_input.cluster.name + "-control-plane-3" in open(tfstate).read():
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
  kubeone_command="ssh-agent && ssh-add /root/.ssh/id_rsa && sleep 3 && kubeone install --manifest kubeone/config-edited.yaml --tfjson " + tfpath
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

###Untaint master nodes for deploying rook-ceph and other system components -- START
config.load_kube_config(kubeconfig)
v1 = client.CoreV1Api()
ret = v1.list_node()
for i in ret.items:
  cmd="export KUBECONFIG=" + kubeconfig + " && " + "kubectl taint nodes " + i.metadata.name + " node-role.kubernetes.io/master-"
  os.system(cmd)
logger.success("All master nodes are untainted")
###Untaint master nodes for deploying rook-ceph and other system components -- END

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
  cluster_file="rook/aws/cluster.yaml"
  with open(cluster_file, 'r') as file :
    filedata = file.read()
elif user_input.cloud.provider == "hetzner":
  cluster_file="rook/hetzner/cluster.yaml"
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
      apply_simple_item_from_yaml(DYNAMIC_CLIENT, "rook/sc/ceph-block-pool-metadata.yaml", verbose=True)
      apply_simple_item_from_yaml(DYNAMIC_CLIENT, "rook/sc/ceph-block-pool-data.yaml", verbose=True)
      apply_simple_item_from_yaml(DYNAMIC_CLIENT, "rook/sc/storage-class.yaml", verbose=True)
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

time.sleep(2) 

end = time.time()
elapsed_time=end-start
logger.success("Completed all steps in a " + str(int(elapsed_time)) + " seconds.") 