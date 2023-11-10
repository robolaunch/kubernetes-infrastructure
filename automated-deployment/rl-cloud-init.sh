#!/bin/bash
set -e;

BLUE='\033[0;34m';
GREEN='\033[0;32m';
RED='\033[0;31m';
NC='\033[0m';
ARCH=$(dpkg --print-architecture)
TIMESTAMP=$(date +%s)
OUTPUT_FILE="out_$TIMESTAMP.log"
export KUBECONFIG="/etc/rancher/k3s/k3s.yaml";
exec 3>&1 >$OUTPUT_FILE 2>&1;
print_global_log () {
    echo -e "${GREEN}$1${NC}" >&3;
}
print_log () {
    echo -e "${GREEN}$1${NC}";
}
print_err () {
    echo -e "${RED}Error: $1${NC}" >&3;
    exit 1;
}
set_cluster_root_domain () {
    CLUSTER_ROOT_DOMAIN=$(kubectl get cm coredns -n kube-system -o jsonpath="{.data.Corefile}" \
        | grep ".local " \
        | awk -F ' ' '{print $2}');
}
set_organization () {
    if [[ -z "${ORGANIZATION}" ]]; then
        print_err "ORGANIZATION should be set";
    else
        ORGANIZATION=$ORGANIZATION;
    fi
}
set_team () {
    if [[ -z "${TEAM}" ]]; then
        print_err "TEAM should be set";
    else
        TEAM=$TEAM;
    fi
}
set_region () {
    if [[ -z "${REGION}" ]]; then
        print_err "REGION should be set";
    else
        REGION=$REGION;
    fi
}
set_cloud_instance () {
    if [[ -z "${CLOUD_INSTANCE}" ]]; then
        print_err "CLOUD_INSTANCE should be set";
    else
        CLOUD_INSTANCE=$CLOUD_INSTANCE;
    fi
}
set_cloud_instance_alias () {
    if [[ -z "${CLOUD_INSTANCE_ALIAS}" ]]; then
        print_err "CLOUD_INSTANCE_ALIAS should be set";
    else
        CLOUD_INSTANCE_ALIAS=$CLOUD_INSTANCE_ALIAS;
    fi
}
set_desired_cluster_cidr () {
    if [[ -z "${DESIRED_CLUSTER_CIDR}" ]]; then
        print_err "DESIRED_CLUSTER_CIDR should be set";
    else
        DESIRED_CLUSTER_CIDR=$DESIRED_CLUSTER_CIDR;
    fi
}
set_desired_service_cidr () {
    if [[ -z "${DESIRED_SERVICE_CIDR}" ]]; then
        print_err "DESIRED_SERVICE_CIDR should be set";
    else
        DESIRED_SERVICE_CIDR=$DESIRED_SERVICE_CIDR;
    fi
}
set_public_ip () {
    if [[ -z "${PUBLIC_IP}" ]]; then
        PUBLIC_IP=$(curl https://ipinfo.io/ip);
    else
        PUBLIC_IP=$PUBLIC_IP;
    fi
}
check_api_server_url () {
    set_public_ip
    CLOUD_INSTANCE_API_SERVER_URL="$SERVER_URL:6443";
}
check_node_name () {
    NODE_NAME=$(kubectl get nodes -l node-role.kubernetes.io/master -o 'jsonpath={.items[*].metadata.name}');
}
check_cluster_cidr () {
    check_node_name;
    CLOUD_INSTANCE_CLUSTER_CIDR=$(kubectl get nodes $NODE_NAME -o jsonpath='{.spec.podCIDR}');
}
check_service_cidr () {
    CLOUD_INSTANCE_SERVICE_CIDR=$(echo '{"apiVersion":"v1","kind":"Service","metadata":{"name":"tst"},"spec":{"clusterIP":"1.1.1.1","ports":[{"port":443}]}}' | kubectl apply -f - 2>&1 | sed 's/.*valid IPs is //');
}
check_inputs () {
    set_organization;
    set_team;
    set_region;
    set_cloud_instance;
    set_cloud_instance_alias;
    set_desired_cluster_cidr;
    set_desired_service_cidr;
}
get_versioning_map () {
    wget https://raw.githubusercontent.com/robolaunch/robolaunch/main/platform.yaml;
}
opening () {
    apt-get update 2>/dev/null 1>/dev/null;
    apt-get install -y figlet 2>/dev/null 1>/dev/null; 
    figlet 'robolaunch' -f slant;
}
copy_start_script () {
    echo "#!/bin/bash" > start_script.sh
    echo "sleep 30" >> start_script.sh
    echo "wan_ip=\$(curl https://ipinfo.io/ip)" >> start_script.sh
    echo "export wan_ip=\$wan_ip" >> start_script.sh
    echo "curl -vk --resolve \$wan_ip:6443:127.0.0.1 https://\$wan_ip:6443/ping" >> start_script.sh
	chmod +x start_script.sh
	cp  start_script.sh /var/lib/cloud/scripts/per-boot/initial-script.sh
}
set_up_k3s () {
    curl -sfL https://get.k3s.io | \
        INSTALL_K3S_VERSION=$K3S_VERSION+k3s1 \
        K3S_KUBECONFIG_MODE="644" \
        INSTALL_K3S_EXEC="  --cluster-cidr=$DESIRED_CLUSTER_CIDR --service-cidr=$DESIRED_SERVICE_CIDR    --cluster-domain=$CLUSTER_DOMAIN.local --disable-network-policy --disable=traefik --disable=local-storage -kube-apiserver-arg oidc-issuer-url=$OIDC_URL --kube-apiserver-arg oidc-client-id=$OIDC_ORGANIZATION_CLIENT_ID --kube-apiserver-arg oidc-username-claim=preferred_username --kube-apiserver-arg oidc-groups-claim=groups" sh -;
    sleep 5;
}
check_cluster () {
    check_api_server_url;
    check_cluster_cidr;
    check_service_cidr;
    set_public_ip
    curl -vk --resolve $PUBLIC_IP:6443:127.0.0.1  https://$PUBLIC_IP:6443/ping;
	cp /etc/rancher/k3s/k3s.yaml /home/ubuntu/k3s.yaml
	chmod 777 /home/ubuntu/k3s.yaml
}
label_node () {
    check_node_name;
    kubectl label --overwrite=true node $NODE_NAME \
        robolaunch.io/platform=$PLATFORM_VERSION \
		robolaunch.io/organization=$ORGANIZATION \
        robolaunch.io/region=$REGION \
        robolaunch.io/team=$TEAM \
        robolaunch.io/cloud-instance=$CLOUD_INSTANCE \
        robolaunch.io/cloud-instance-alias=$CLOUD_INSTANCE_ALIAS \
        submariner.io/gateway="true";
}
update_helm_repositories () {
	helm repo add openebs https://openebs.github.io/charts 
	helm repo add oauth2-proxy https://oauth2-proxy.github.io/manifests
	helm repo add jetstack https://charts.jetstack.io
	helm repo add robolaunch https://robolaunch.github.io/charts
	helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
    helm repo update;
}
install_openebs () {
    helm install openebs openebs/openebs \
    --namespace openebs \
    --create-namespace;
    sleep 5;
    kubectl patch storageclass openebs-hostpath -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}';
}
install_nvidia_runtime_class () {
    cat << EOF | kubectl apply -f -
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: nvidia
handler: nvidia
EOF
}
install_gpu_feature_discovery () {
  #   echo "image:
  # repository: quay.io/robolaunchio/node-feature-discovery
  # tag: v0.14.3" > $DIR_PATH/node-feature-discovery/values.yaml;
    wget https://github.com/robolaunch/on-premise/releases/download/0.1.2-prerelease.10/gpu-feature-discovery-0.8.2.tgz
    helm upgrade --install \
      nfd gpu-feature-discovery-0.8.2.tgz \
      --namespace gpu-feature-discovery \
      --create-namespace \
	  --set runtimeClassName=nvidia
      # -f $DIR_PATH/node-feature-discovery/values.yaml;
}
install_node_feature_discovery () {
    echo "image:
  repository: quay.io/robolaunchio/node-feature-discovery
  tag: v0.14.3" > node-feature-discovery-values.yaml;
    wget https://github.com/robolaunch/on-premise/releases/download/0.1.2-prerelease.10/node-feature-discovery-chart-0.14.3.tgz
    helm upgrade --install \
      nfd node-feature-discovery-chart-0.14.3.tgz \
      --namespace nfd \
      --create-namespace \
      -f node-feature-discovery-values.yaml;
}
install_nvidia_device_plugin () {
    echo "version: v1
sharing:
  timeSlicing:
    resources:
    - name: nvidia.com/gpu
      replicas: 20" > nvidia-device-plugin-config.yaml
    wget https://github.com/robolaunch/on-premise/releases/download/0.1.2-prerelease.10/nvidia-device-plugin-0.14.2.tgz;
    helm upgrade -i nvdp ./nvidia-device-plugin-0.14.2.tgz \
    --version=0.14.2 \
    --namespace nvidia-device-plugin \
    --create-namespace \
    --set-file config.map.config=nvidia-device-plugin-config.yaml \
    --set runtimeClassName=nvidia;
    rm -rf nvidia-device-plugin-0.14.2.tgz;
    rm -rf nvidia-device-plugin-config.yaml;
}
install_cert_manager () {
    kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/$CERT_MANAGER_VERSION/cert-manager.yaml;
    # TODO: Check if cert-manager is up & running.
    sleep 10;
}
create_super_admin_crb () {
	echo "kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: $ORGANIZATION-super-admin-role
rules:
  - apiGroups: ['*']
    resources: ['*']
    verbs: ['*']
---
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: $ORGANIZATION-super-admin-crb
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: $ORGANIZATION-super-admin-role
subjects:
- kind: Group
  name: $GROUP_SUPER_ADMIN
  apiGroup: rbac.authorization.k8s.io" > crb.yaml
	kubectl create -f crb.yaml
	rm -rf crb.yaml
}
create_admin_crb () {
	echo "kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: $ORGANIZATION-admin-role
rules:                                                                                                                                                                                                    
- apiGroups:                                                                                                                                                                                              
  - '*'                                                                                                                                                                                                   
  resources:                                                                                                                                                                                              
  - nodes                                                                                                                                                                                                 
  - namespaces                                                                                                                                                                                            
  - metricsexporters                                                                                                                                                                                      
  - secrets                                                                                                                                                                                               
  - roles                                                                                                                                                                                                 
  - rolebindings                                                                                                                                                                                          
  - pods                                                                                                                                                                                                  
  verbs:                                                                                                                                                                                                  
  - get                                                                                                                                                                                                   
  - list                                                                                                                                                                                                  
- apiGroups:                                                                                                                                                                                              
  - '*'                                                                                                                                                                                                   
  resources:                                                                                                                                                                                              
  - secrets                                                                                                                                                                                               
  - namespaces                                                                                                                                                                                            
  verbs:                                                                                                                                                                                                  
  - create                                                                                                                                                                                                
- apiGroups:                                                                                                                                                                                              
  - '*'                                                                                                                                                                                                   
  resources:                                                                                                                                                                                              
  - roles                                                                                                                                                                                                 
  - rolebindings                                                                                                                                                                                          
  verbs:                                                                                                                                                                                                  
  - create                                                                                                                                                                                                
  - bind                                                                                                                                                                                                  
  - escalate 
---
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: $ORGANIZATION-admin-crb
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: $ORGANIZATION-admin-role
subjects:
- kind: Group
  name: $GROUP
  apiGroup: rbac.authorization.k8s.io" > user-crb.yaml
	kubectl create -f user-crb.yaml
	rm -rf user-crb.yaml
}
install_ingress_nginx () {
	echo "controller:
  kind: DaemonSet
  hostPort:
    enabled: true
  hostNetwork: true
  ingressClassResource:
    name: nginx
    enabled: true
    default: true
defaultBackend:
  enabled: true" > ingress-values.yaml
	helm upgrade --install ingress-nginx ingress-nginx --repo https://kubernetes.github.io/ingress-nginx --namespace ingress-nginx --create-namespace -f ingress-values.yaml --set controller.service.type=NodePort  --version 4.4.2
	rm -rf ingress-values.yaml
	sleep 2;
}
install_oauth2_proxy () {
	echo "replicaCount: 1
config:
  clientID: $OIDC_ORGANIZATION_CLIENT_ID
  clientSecret: $OIDC_ORGANIZATION_CLIENT_SECRET
  cookieSecret: $COOKIE_SECRET
  configFile: |-
    provider = 'keycloak-oidc'
    provider_display_name = 'Keycloak'
    oidc_issuer_url = '$OIDC_URL'
    email_domains = ['*']
    scope = 'openid profile email'
    whitelist_domains = '.$DOMAIN'
    cookie_domains= '.$DOMAIN'
    pass_authorization_header = true
    pass_access_token = true
    pass_user_headers = true
    set_authorization_header = true
    set_xauthrequest = true
    cookie_refresh = false
    cookie_expire = '12h'
    redirect_url= 'https://$SERVER_URL/oauth2/callback'
    allowed_groups= '$GROUP'" > oauth2-values.yaml
	helm upgrade -i --values oauth2-values.yaml oauth2-proxy oauth2-proxy/oauth2-proxy --namespace oauth2-proxy --create-namespace
	rm -rf oauth2-values.yaml
	sleep 2;
}
install_proxy_ingress () {
	echo "apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: oauth2-proxy
  namespace: oauth2-proxy
  annotations:
    nginx.ingress.kubernetes.io/proxy-buffer-size: '16k'
    nginx.ingress.kubernetes.io/proxy-buffers-number: '4'
spec:
  tls:
  - hosts:
    - $SERVER_URL
    secretName: prod-tls
  rules:
  - host: $SERVER_URL
    http:
      paths:
      - path: /oauth2
        pathType: Prefix
        backend:
          service:
            name: oauth2-proxy
            port:
              number: 80
  ingressClassName: nginx" > proxy-ingress.yaml
	kubectl create -f proxy-ingress.yaml
	rm -rf proxy-ingress.yaml
}
install_operator_suite () {    

    RO_HELM_INSTALL_SUCCEEDED="false"
    while [ "$RO_HELM_INSTALL_SUCCEEDED" != "true" ]
    do 
        RO_HELM_INSTALL_SUCCEEDED="true"
        helm upgrade -i \
            robot-operator robolaunch/robot-operator \
            --namespace robot-system \
            --create-namespace \
            --version $ROBOT_OPERATOR_CHART_VERSION || RO_HELM_INSTALL_SUCCEEDED="false";
        sleep 1;
    done

}
deploy_metrics_namespace () {
    cat << EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: rl-metrics
EOF
}
deploy_metrics_exporter () {
    apt-get install -y net-tools
	DEFAULT_NETWORK_INTERFACE=$(route | grep '^default' | grep -o '[^ ]*$')
    cat << EOF | kubectl apply -f -
apiVersion: robot.roboscale.io/v1alpha1
kind: MetricsExporter
metadata:
  name: rl-metrics
  namespace: rl-metrics
spec:
  gpu:
    track: true
    interval: 5
  storage:
    track: true
    interval: 5
  network:
    track: true
    interval: 3
    interfaces:
    - $DEFAULT_NETWORK_INTERFACE
EOF
}
sleep 10
(get_versioning_map)
sleep 3
if [[ -z "${PLATFORM_VERSION}" ]]; then
    PLATFORM_VERSION=$(yq '.versions[0].version' < platform.yaml)
fi
sleep 3
VERSION_SELECTOR_STR='.versions[] | select(.version == "'"$PLATFORM_VERSION"'")'
K3S_VERSION=v$(yq ''"${VERSION_SELECTOR_STR}"' | .roboticsCloud.kubernetes.version' < platform.yaml)
CERT_MANAGER_VERSION=$(yq ''"${VERSION_SELECTOR_STR}"' | .roboticsCloud.kubernetes.components.cert-manager.version' < platform.yaml)
CONNECTION_HUB_OPERATOR_CHART_VERSION=$(yq ''"${VERSION_SELECTOR_STR}"' | .roboticsCloud.kubernetes.operators.connectionHub.helm.version' < platform.yaml)
CONNECTION_HUB_RESOURCE_URL=$(yq ''"${VERSION_SELECTOR_STR}"' | .roboticsCloud.kubernetes.operators.connectionHub.resources.cloudInstance' < platform.yaml)
ROBOT_OPERATOR_CHART_VERSION=$(yq ''"${VERSION_SELECTOR_STR}"' | .roboticsCloud.kubernetes.operators.robot.helm.version' < platform.yaml)
FLEET_OPERATOR_CHART_VERSION=$(yq ''"${VERSION_SELECTOR_STR}"' | .roboticsCloud.kubernetes.operators.fleet.helm.version' < platform.yaml)
opening >&3
(check_inputs)
print_global_log "Copying Start Script";
(copy_start_script)
print_global_log "Setting up k3s cluster";
(set_up_k3s)
print_global_log "Checking cluster health";
(check_cluster)
print_global_log "Labeling node";
(label_node)
print_global_log "Updating Helm repositories";
(update_helm_repositories)
print_global_log "Creating admin crb";
(create_admin_crb)
print_global_log "Creating super admin crb";
(create_super_admin_crb)
print_global_log "Installing ingress";
(install_ingress_nginx)
print_global_log "Installing oauth2-proxy";
(install_oauth2_proxy)
print_global_log "Installing openebs";
(install_openebs)
print_global_log "Installing cert-manager";
(install_cert_manager)
print_global_log "Installing proxy-ingress";
(install_proxy_ingress)
print_global_log "Installing NVIDIA runtime";
(install_nvidia_runtime_class)
print_global_log "Installing GPU feature discovery...";
(install_gpu_feature_discovery)
print_global_log "Installing NVIDIA device plugin";
(install_nvidia_device_plugin)
print_global_log "Installing robolaunch Operator Suite";
(install_operator_suite)
print_global_log "Deploying Metric Namespace";
(deploy_metrics_namespace)
print_global_log "Deploying Metric Exporter";
(deploy_metrics_exporter)
