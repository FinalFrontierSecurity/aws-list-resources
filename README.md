# aws-list-resources

Uses the AWS Cloud Control API to list resources that are present in a given AWS account and region(s). Discovered
resources are written to a JSON output file. See the accompanying blog posts 
[here](https://medium.com/@michael.kirchner/how-to-list-all-resources-in-your-aws-account-c3f18061f71b) and 
[here](https://medium.com/@michael.kirchner/exploring-aws-resource-explorer-825498b5307d).


## Usage

Make sure you have AWS credentials configured for your target account. This can either be done using [environment 
variables](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-envvars.html) or by specifying a [named 
profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html) in the optional `--profile` 
argument. Read-only IAM permissions are sufficient. 

When running the script, it is recommended to include the `us-east-1` region in addition to the region(s) that your workload uses primarily. This ensures that resources of global AWS services are captured as well.

Use `--resource-scope all` to set the scan to all resource types provided by Cloud Control. By default, it will only identify resources types listed in the `essential-resource-types.txt` file.
Two output file formats are supported - JSON and CSV. Switch between these with the `--output-format` flag. CSV is default.
The output can either list the identified resources by name or by count. Switch between these options with `--output-type`. Count is default

Example run:

```bash
pip install -r requirements.txt

python aws_list_resources.py --regions us-east-1,eu-central-1
```


## Notes

* The script will only be able to discover resources that are currently supported by the AWS Cloud Control API and
  offer support for the `List` operation:

  https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html
  
  It is further restricted to those resources where the `List` operation does not expect any additional parameters.

* If the IAM user or role you use to run the script does not have permissions to interact with certain AWS services or
  regions, those resources will be missed. Note that permissions can be restricted on different levels, such as SCPs, 
  identity-based polices, etc. The JSON output file will contain a list of resource types where listing was denied.

* The JSON output file will also contain default resources that were created by AWS, independent of whether you 
  actually used the service or not.


## Example output file

Truncated example JSON output file:
```json
{
  "_metadata": {
    "account_id": "123456789012",
    "account_principal": "arn:aws:iam::123456789012:user/myuser",
    "run_timestamp": "20221020084237"
    // ...
  },
  "regions": {
    "us-east-1": {
      "AWS::Athena::DataCatalog": [
        "AwsDataCatalog"
      ],
      "AWS::CloudFront::CachePolicy": [
        "08627262-05a9-4f76-9ded-b50ca2e3a84f",
        "2e54312d-136d-493c-8eb9-b001f22f67d2",
        "4135ea2d-6df8-44a3-9df3-4b5a84be39ad",
        "658327ea-f89d-4fab-a63d-7e88639e58f6",
        "b2884449-e4de-46a7-ac36-70bc7f1ddd6d"
      ],
      "AWS::EC2::DHCPOptions": [
        "dopt-0aff9c4854b33dc5c"
      ],
      "AWS::EC2::InternetGateway": [
        "igw-0090532d0f608e279"
      ],
      "AWS::EC2::NetworkAcl": [
        "acl-0451d5fc3be271330"
      ],
      "AWS::EC2::RouteTable": [
        "rtb-077ff6c625794e4fe"
      ],
      "AWS::IAM::Role": [
        "AWSServiceRoleForCloudTrail",
        "AWSServiceRoleForGlobalAccelerator",
        "AWSServiceRoleForOrganizations",
        "AWSServiceRoleForSupport",
        "AWSServiceRoleForTrustedAdvisor",
        "OrganizationAccountAccessRole"
      ],
      // ...
    }
  }
}
```
