import json
import sys

# using variables for the import files
SUBNET_FILE = "subnets_live.json" 
RTS_FILE = "rts_live.json"

if len(sys.argv) == 3:
    SUBNET_FILE = sys.argv[1]
    RTS_FILE = sys.argv[2]
elif len(sys.argv) != 1:
    print("Usage: python3 subnet_reachability.py [SUBNET_FILE RTS_FILE]")
    sys.exit(1)

#try loading the files and if there are any errors print a message and exit
try:
    #reading the SUBNET_FILE and loading it into subnets and print what was
    #loaded and the counts
    with open(SUBNET_FILE, "r") as f:
        subnets = json.load(f)
    #reading the RTS_FILE and loading it into rts
    with open(RTS_FILE, "r") as f:
        rts = json.load(f)
except json.JSONDecodeError as e:
    print(f"{e}")
    sys.exit(1)
except FileNotFoundError as e:
    print(f"{e}")
    sys.exit(1)
print(f"Loaded {len(subnets)} subnets and {len(rts)} route tables")   

#building a dict of subnet is and rt that has explicit rt associaitons (SubnetId in rt[assoc])
def build_subnet_rt_lookup(rts):
    subnet_by_rts = {}
    for rtb in rts:
        for assoc in rtb["Associations"]:
            if "SubnetId" in assoc:
                subnet_by_rts[assoc.get("SubnetId")] = rtb
    return subnet_by_rts
    
#buidling a dict of vpc is and ther route tables    
def build_main_rt_by_vpc(rts):
    vpc_by_rts = {}
    for rtb in rts:
        for assoc in rtb["Associations"]:
            if assoc.get("Main") is True:
                vpc_by_rts[rtb["VpcId"]] = rtb
    return vpc_by_rts
            
#checking if a route table has a default route (target is gatewayid if not get the natgateway id)
def get_default_route_target(rt):
    for route in rt["Routes"]:
        if route.get("DestinationCidrBlock") == "0.0.0.0/0":
            target = route.get("GatewayId") or route.get("NatGatewayId")
            return target
    return None    

def classify_subnet(target):
   if target is None:
       return "isolated"
   elif target.startswith("igw-"):
       return "public"
   elif target.startswith("nat-"):
       return "private-egress"
   else:
       return "other"
   
   
def is_mismatch(classification, auto_ip):
    is_public = classification == "public"
    return is_public != auto_ip


mismatch_count = 0    
main_by_vpc = build_main_rt_by_vpc(rts)  
subnet_rt_lookup = build_subnet_rt_lookup(rts)
print(f"Explicit associations: {len(subnet_rt_lookup)}")
print(f"VPCs with a main route table: {len(main_by_vpc)}")
for subnet in subnets:
    subnet_id = subnet["SubnetId"]
    rt = subnet_rt_lookup.get(subnet_id)
    if rt is None:
        rt = main_by_vpc.get(subnet["VpcId"])
        source = "main"
    else:
        source = "explicit"
    target = get_default_route_target(rt)
    classification = classify_subnet(target)
    auto_ip = subnet["MapPublicIpOnLaunch"]
    mismatch = is_mismatch(classification, auto_ip)
    
    if mismatch_count is True:
        mismatch_count += 1
    print(f"{subnet_id}  {rt['RouteTableId']}  {source}  {target}  {classification}  auto_ip={auto_ip}  mismatch={mismatch}")
    
print(f"Mismatches: {mismatch_count}")
if mismatch_count > 0:
    print(f"FAIL")
    sys.exit(1)
else:
    print(f"PASS")

    
