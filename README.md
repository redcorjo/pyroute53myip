
# pyroute53myip

## Description 

This python tool pyroute53myip is useful to allow automate updating of a public DNS record hosted at Internet based in the public internet address from home. It is a quite typical scenario running at a domestic raspberry-pi tiny instance

## Author

Name: redcorjo 
Email: jordipromotions@gmail.com


## Config file structure

The tool self encrypt the AWS credentials initially added on clear. They are encrypted and useable only from the same host they were encrypted. First time the tool is executed, at command line there is a wizard asking for initial values.


Config file can be defined using env variable PYROUTE53MYIP_CONFIG

```
[aws]
aws_access_key_id = <access_key>
aws_secret_access_key = <secret_key>

[dns]
zoneid = <my_aws_zoneid>
record_set = my.domain.com
public_ip = 1.2.3.4

[scheduler]
frequency = 60

[mqtt]
mqtt_server = 127.0.0.1
mqtt_topic = pyroute53myip
```

## Usage

```sh
python3 -m pip install pyroute53myip
python3 -m pyroute53myip
```

Version: 2023012900