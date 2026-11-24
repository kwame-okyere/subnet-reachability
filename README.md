# Subnet reachability check

I wrote this to answer a simple question: which of my AWS subnets are actually public?

## Why I built it

You can't tell from a subnet's name, and you can't tell from the "auto-assign public IP" setting either. What makes a subnet public is its route table: 
if the route table it uses has a default route (0.0.0.0/0) to an internet gateway, it's public.

The catch is that a subnet doesn't tell you which route table it uses. You have to look at the route tables' associations instead.
And if a subnet isn't explicitly associated with any route table, it quietly uses its VPC's main route table.
So if someone adds an internet route to the main table, every subnet that was never associated becomes public, whatever it's called.

## How it works

1. Load the subnets and route tables (two JSON files saved from the AWS API).
2. Build a lookup of explicit associations: subnet ID → route table.
3. Build a lookup of main route tables: VPC ID → route table. It's keyed by VPC because every VPC has its own main route table.
4. For each subnet, use its explicit route table if it has one. If not, use the main route table of its VPC.
5. Find the default route in that table and classify the subnet:
   - igw-... → public
   - nat-... → private-egress
   - no default route → isolated
   - anything else (for example a transit gateway) → other
6. Compare that with the subnet's MapPublicIpOnLaunch setting and flag a mismatch when they disagree.

A mismatch can go two ways. A public subnet that doesn't give instances a public IP means they can't actually use the internet gateway. A non-public subnet that does give out public IPs is a problem waiting to happen: if its routing changes, those instances are reachable from the internet straight away.

## Running it

You need Python 3 and the AWS CLI with read-only EC2 access.

Save the data first:

```
aws ec2 describe-subnets --query "Subnets" > subnets_live.json
aws ec2 describe-route-tables --query "RouteTables" > rts_live.json
```

Then run:

```
python3 subnet_reachability.py
```

The *_live.json files are in .gitignore because they contain the account ID.

You can also point it at other data by giving the subnets file and the route tables file, in that order:

```
python3 subnet_reachability.py tests/subnets_test.json tests/rts_test.json
```

If you give one file name, or more than two, it prints how to use it and exits with code 1.

## Example output

This is from the default VPC in eu-west-2, which has 4 subnets and no explicit associations:

```
Loaded 4 subnets and 1 route tables
Explicit associations: 0
VPCs with a main route table: 1
subnet-056ab3edf953b81d2  rtb-0c33e50646e6333b1  main  igw-0dfed8ff482044fa3  public  auto_ip=True  mismatch=False
subnet-0d342050732eef89d  rtb-0c33e50646e6333b1  main  igw-0dfed8ff482044fa3  public  auto_ip=True  mismatch=False
subnet-0d2b1249f4f2e592e  rtb-0c33e50646e6333b1  main  igw-0dfed8ff482044fa3  public  auto_ip=True  mismatch=False
subnet-00813ec961b881dac  rtb-0c33e50646e6333b1  main  igw-0dfed8ff482044fa3  public  auto_ip=True  mismatch=False
```


## Testing
The `tests/` folder has made-up data (no real account details) covering every case the script handles: a public subnet, a NAT subnet, an isolated subnet, explicit route table associations, a second VPC, and two mismatches.

Running the script on it should report `Mismatches: 2`, print `FAIL` and exit with code 1. With no mismatches it prints `PASS` and exits with 0, so a CI pipeline can use the exit code to pass or fail a change.

This test data found a bug that my live account couldn't show: the script flagged mismatches correctly but the count stayed at zero.


## Next steps

- Handle AWS API errors properly (for example missing permissions) instead of crashing.
- Run the test data automatically on every pull request.



## What I learned

- A subnet is public because of its route table, not its name.
- Forgetting a route table association doesn't cause an error. The subnet just falls back to the main route table, which is why it's easy to miss.
- My first version of the main-route-table lookup only worked with one VPC. It looked fine on my account and would have been wrong anywhere with more than one.

