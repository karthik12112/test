import boto3
import datetime
import time
from datetime import timedelta
from datetime import date
import pytz
utc=pytz.UTC
today = date.today()
ec2client = boto3.client('ec2')
ec2 = boto3.resource('ec2')
paginator = ec2client.get_paginator('describe_instances')

def lambda_handler(event, context):
    Instance_details = {}
    Instance_details["Id_Tag"]= {}
    response_iterator = paginator.paginate(Filters=[{
        'Name': 'tag:Snowflake',
        'Values': ['True', 'SysOps', 'sysops', 'Sysops']}])
    for page in response_iterator:
      for i in range(len(page['Reservations'])):
        a = page['Reservations'][i]['Instances'][0]['InstanceId']
        try:
            ec2_tags = page['Reservations'][i]['Instances'][0]['Tags']
            for each in range(len(ec2_tags)):
                tag = ec2_tags[each]
                if tag['Key']=='Name':
                    if tag['Value'] == []:
                        Instance_details["Id_Tag"][a] = 'no-tag'
                    else:
                        Instance_details["Id_Tag"][a] = tag['Value']
        except Exception as e: print(e)

    Instance_details["image_id"]= []
    for key, value in Instance_details["Id_Tag"].items():
        try:
            response = ec2client.create_image(
            InstanceId=key,
            Name=str(value)+"-"+str(date.today()),
            #Name=str(value)+"-patching-"+str(date.today()),
            NoReboot=True
            )
            Instance_details["image_id"].append(response['ImageId'])
        except:
            pass

    time.sleep(10)
    Instance_details["image_description"]= []
    for each in Instance_details["image_id"]:
        try:
            ec2.Image(each).create_tags(Tags=[{'Key': 'Name', 'Value': 'Snowflake'},])
            Instance_details["image_description"].append(ec2client.describe_images(ImageIds=[each,]))
        except:
            pass

    Instance_details["snap_id"]= []
    for description in range(len(Instance_details["image_description"])):
        try:
            for i in range(len(Instance_details["image_description"][description]['Images'][0]['BlockDeviceMappings'])):
                Instance_details["snap_id"].append(Instance_details["image_description"][description]['Images'][0]['BlockDeviceMappings'][i]['Ebs']['SnapshotId'])
        except:
            pass

    for id in Instance_details["snap_id"]:
        try:
            response = ec2client.create_tags(
                Resources=[id,],
                Tags=[{'Key': 'Snowflake','Value': 'True',},],)
        except Exception as e:
            print("Error creating tags.  \n {}".format(e))

    image_description_to_delete = ec2client.describe_images(Filters=[{'Name': 'tag:Name','Values': ['Snowflake',]}])
    Instance_details["Images"]= {}
    for num in range(len(image_description_to_delete['Images'])):
        Instance_details["Images"][image_description_to_delete['Images'][num]['ImageId']] = image_description_to_delete['Images'][num]['Name']

    delete_date = date.today() - timedelta(days=7)
    format_str = '%Y-%m-%d'
    for key, value in Instance_details["Images"].items():
        try:
            tag_date = value[-10:]
            datetime_obj = (datetime.datetime.strptime(tag_date, format_str)).date()
            if datetime_obj <= delete_date:
                print ("deleting image:{}".format(key))
                ec2client.deregister_image(ImageId=key)
        except Exception as e:
            print("Error deregistering image. \n {}".format(e))

    snap_paginator = ec2client.get_paginator('describe_snapshots')
    snapshot_description = snap_paginator.paginate(Filters=[{'Name': 'tag:Snowflake','Values': ['True',]},])
    delete_time = datetime.datetime.utcnow() - timedelta(days=9)
    for page in snapshot_description:
        for each in range(len(page['Snapshots'])):
            for tag in range(len(page['Snapshots'][each]['Tags'])):
                if page['Snapshots'][each]['Tags'][tag]['Key']=='Snowflake':
                    if  page['Snapshots'][each]['StartTime'].date() <= utc.localize(delete_time).date():
                        try:
                            ec2client.delete_snapshot(SnapshotId=page['Snapshots'][each]['SnapshotId'])
                            print("Deleting snapshot: {}").format(page['Snapshots'][each]['SnapshotId'])
                        except Exception as e:
                            print("Error deleting: \n{}".format(e))
