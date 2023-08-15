#!/usr/bin/env python3

import argparse
import boto3
import botocore.config
import concurrent.futures
import datetime
import json
import sys
import copy
import csv


boto_config = botocore.config.Config(retries={"total_max_attempts": 5, "mode": "standard"})


def get_available_resource_types(boto_session, region):
    """
    Returns a list of resource types that are supported in a region by querying the CloudFormation registry.
    Examples: AWS::EC2::RouteTable, AWS::IAM::Role, AWS::KMS::Key, etc.
    """
    resource_types = set()
    cloudformation_client = boto_session.client("cloudformation", region_name=region, config=boto_config)

    provisioning_types = ("FULLY_MUTABLE", "IMMUTABLE")
    for provisioning_type in provisioning_types:
        call_params = {
            "Type": "RESOURCE",
            "Visibility": "PUBLIC",
            "ProvisioningType": provisioning_type,
            "DeprecatedStatus": "LIVE",
            "Filters": {"Category": "AWS_TYPES"},
        }
        while True:
            cloudformation_response = cloudformation_client.list_types(**call_params)
            for type in cloudformation_response["TypeSummaries"]:
                resource_types.add(type["TypeName"])
            try:
                call_params["NextToken"] = cloudformation_response["NextToken"]
            except KeyError:
                break

    return sorted(resource_types)

def get_essential_resource_types():
    """
    Returns a list of essential resource types from a txt file when a full list is not desired
    """
    return open('essential-resource-types.txt').read().splitlines()

def get_resources(boto_session, region, resource_type):
    """
    Returns a list of resources of the given resource type discovered in the given region. Uses the "List" operation
    of the Cloud Control API. If the API call failed, an empty list is returned. If the API call likely failed because
    of permission issues, an additional flag is set in the return value.
    """
    print("{}, {}".format(region, resource_type))
    collected_resources = []
    list_operation_was_denied = False
    cloudcontrol_client = boto_session.client("cloudcontrol", region_name=region, config=boto_config)

    call_params = {"TypeName": resource_type}
    try:
        while True:
            cloudcontrol_response = cloudcontrol_client.list_resources(**call_params)
            for resource in cloudcontrol_response["ResourceDescriptions"]:
                collected_resources.append(resource["Identifier"])
            try:
                call_params["NextToken"] = cloudcontrol_response["NextToken"]
            except KeyError:
                break

    except Exception as ex:
        # There is unfortunately a long and non-uniform list of exceptions that can occur with the Cloud Control API,
        # presumably because it just passes through the exceptions of the underlying services. Examples for when the
        # "List" operation requires additional parameters or when the caller lacks permissions for an API call:
        # UnsupportedActionException, InvalidRequestException, GeneralServiceException, ResourceNotFoundException,
        # HandlerInternalFailureException, AccessDeniedException, AuthorizationError, etc. They are thus handled by
        # this broad except clause. The end result is the same: resources for this resource type cannot be listed.

        # Flag when the "List" operation was likely denied due to a lack of permissions
        exception_msg = str(ex).lower()
        for keyword in ("denied", "authorization", "authorized"):
            if keyword in exception_msg:
                list_operation_was_denied = True
                break

    return (resource_type, list_operation_was_denied, sorted(collected_resources))

def get_counts(result_collection):
    result_count_collection = copy.deepcopy(result_collection)
    result_count_collection['regions'] = {}
    for region in result_collection['regions']:
        result_count_collection['regions'][region] = {}
        for resource_type in result_collection['regions'][region]:
            result_count_collection['regions'][region][resource_type] = len(result_collection['regions'][region][resource_type])
    return result_count_collection
            
def write_to_json(result_collection, output_type):
    output_file_name = "resources_{}_{}.json".format(sts_response["Account"], run_timestamp)
    if output_type == "COUNT":
        result_collection = get_counts(result_collection)
    with open(output_file_name, "w") as out_file:
        json.dump(result_collection, out_file, indent=2, sort_keys=True)

    print("Output file written to {}".format(output_file_name))
            
def write_to_csv(result_collection, output_type):
    print(result_collection)
    output_file_name = "resources_{}_{}.csv".format(sts_response["Account"], run_timestamp)
    headers = []
    rows = []
    if output_type == "COUNT":
        result_collection = get_counts(result_collection)
        headers = ['Resource Type', 'Region', 'Count']
        for region in result_collection['regions']:
            for resource_type in result_collection['regions'][region]:
                rows.append([resource_type, region, str(result_collection['regions'][region][resource_type])])
    else:
        headers = ['Resource Type', 'Region', 'Resource']
        for region in result_collection['regions']:
            for resource_type in result_collection['regions'][region]:
                for resource in result_collection['regions'][region][resource_type]:
                    rows.append([resource_type, region, resource])
    with open(output_file_name, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(headers)
        writer.writerows(rows)

    print("Output file written to {}".format(output_file_name))

if __name__ == "__main__":
    # Check runtime environment
    if sys.version_info[0] < 3:
        print("Python version 3 required")
        sys.exit(1)

    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("--regions", required=True, nargs=1, help="comma-separated list of targeted AWS regions")
    parser.add_argument("--profile", required=False, nargs=1, help="optional named AWS profile to use")
    parser.add_argument("--resource-scope",required=False, nargs=1, help="resouce scheme to query",choices=['all','essential'])
    parser.add_argument("--output-type", required=False, nargs=1, help="retrieve a count or name of each resource found", choices=['count','resource'])
    parser.add_argument("--output-format", required=False, nargs=1, choices=['csv', 'json'])

    args = parser.parse_args()
    target_regions = [region for region in args.regions[0].split(",") if region]
    profile = args.profile[0] if args.profile else None
    resource_scope = args.resource_scope[0].upper() if args.resource_scope else "ESSENTIAL"
    output_type = args.output_type[0].upper() if args.output_type else "COUNT"
    print(output_type)
    output_format = args.output_format[0].upper() if args.output_format else "CSV"
    boto_session = boto3.session.Session(profile_name=profile)

    # Test for valid credentials
    sts_client = boto_session.client("sts", config=boto_config)
    try:
        sts_response = sts_client.get_caller_identity()
    except:
        print("No or invalid AWS credentials configured")
        sys.exit(1)

    # Prepare result collection structure
    run_timestamp = datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")
    result_collection = {
        "_metadata": {
            "account_id": sts_response["Account"],
            "account_principal": sts_response["Arn"],
            "denied_list_operations": {},
            "run_timestamp": run_timestamp,
        },
        "regions": {},
    }
    for region in target_regions:
        result_collection["regions"][region] = {}
        result_collection["_metadata"]["denied_list_operations"][region] = []

    # Collect resources for each target region
    print("Analyzing account ID {}".format(sts_response["Account"]))
    for region in target_regions:
        if resource_scope == "ALL":
            resource_types = get_available_resource_types(boto_session, region)
        elif resource_scope == "ESSENTIAL":
            resource_types = get_essential_resource_types()
        else:
            raise Exception("Resource scope must either be ALL or ESSENTIAL")

        # Using a higher number of threads unfortunately leads to API throttling instead of being faster
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            for resource_type in resource_types:
                future = executor.submit(get_resources, boto_session, region, resource_type)
                futures.append(future)

            for future in concurrent.futures.as_completed(futures):
                resource_type, list_operation_was_denied, resources = future.result()
                if list_operation_was_denied:
                    result_collection["_metadata"]["denied_list_operations"][region].append(resource_type)
                if resources:
                    result_collection["regions"][region][resource_type] = resources

        result_collection["_metadata"]["denied_list_operations"][region].sort()

    if output_format == "JSON":
        write_to_json(result_collection, output_type)
    else:
        write_to_csv(result_collection, output_type)