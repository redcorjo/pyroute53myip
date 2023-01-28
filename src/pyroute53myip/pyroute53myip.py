# Generated using pyarchetype template
# pip install pyarchetype
# git clone https://github.com/redcorjo/pyarchetype.git
import logging, os
import dns.resolver
import boto3
import paho.mqtt.client as paho
import socket
import base64
import configparser
from pyeasyencrypt.pyeasyencrypt import encrypt_string, decrypt_string
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.background import BlockingScheduler
import datetime
import time

LOGLEVEL = os.getenv("DEBUG", "INFO").upper()
if LOGLEVEL == "DEBUG":
    level = logging.DEBUG
elif LOGLEVEL == "INFO":
    level = logging.INFO
elif LOGLEVEL == "WARNING" or LOGLEVEL == "WARN":
    level = logging.WARNING
elif LOGLEVEL == "ERROR":
    level = logging.ERROR
else:
    level = logging.INFO

ENVIRONMENT = os.environ.get("ENVIRONMENT", "prod").lower()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
stream_handler = logging.StreamHandler()
logging_formatter = logging.Formatter(
    '%(levelname)-8s [%(filename)s:%(lineno)d] (' + ENVIRONMENT + ') - %(message)s')
stream_handler.setFormatter(logging_formatter)
logger.addHandler(stream_handler)

class Pyroute53myip():

    my_ip = None
    my_resolver = None
    scheduler = None
    frequency = 60
    config_file = os.path.dirname(os.path.abspath(__file__)) + "/pyroute53myip.ini"

    def __init__(self):
        logger.debug("Initializing the class")
        config_file_template = os.path.dirname(os.path.abspath(__file__)) + "/pyroute53myip.ini"
        config_file = os.getenv("PYROUTE53MYIP_CONFIG", config_file_template)
        self.config_file = config_file
        self.my_resolver = dns.resolver.Resolver()
        my_ip = self.getConfig("public_ip", section="dns")
        if my_ip == None:
            my_ip = self.get_my_public_ip()
            self._update_config("dns", "public_ip", my_ip)
        self.my_ip = my_ip

    def schedule_daemon(self):
        logger.info("Initialize scheduler")
        if self.scheduler == None:
            #self.scheduler = BackgroundScheduler()
            self.scheduler = BlockingScheduler()
        frequency = self.getConfig("frequency", section="scheduler")
        frequency = int(frequency)
        self.frequency = frequency
        logger.info(f"Schedule daemon with frequency={self.frequency}")
        self.scheduler.add_job(self.update_my_public_ip, "interval", minutes=frequency, next_run_time=datetime.datetime.now())
        self.scheduler.start()

    def get_my_public_ip(self):
        # dig +short myip.opendns.com @resolver1.opendns.com
        logger.debug("Get my IP")
        A_SERVER_records = self._query_records("resolver1.opendns.com")
        self.my_resolver.nameservers = A_SERVER_records
        my_ip_records = self._query_records("myip.opendns.com")
        my_ip = my_ip_records[0]
        logger.info(f"my_ip={my_ip}")
        return my_ip

    def update_my_public_ip(self, zoneid=None, record_set=None, region="eu-west-3", ttl=None, force_update=False):
        my_public_ip = self.get_my_public_ip()
        if ( my_public_ip != self.my_ip and self.my_ip != None ) or force_update == True :
            AWS_ACCESS_KEY_ID = self.getConfig("AWS_ACCESS_KEY_ID", section="aws")
            AWS_SECRET_ACCESS_KEY = self.getConfig("AWS_SECRET_ACCESS_KEY", section="aws")
            if ttl == None:
                ttl = self.getConfig("ttl", section="dns")
            if ttl == None:
                ttl = 600
            ttl = int(ttl)
            if zoneid == None:
                zoneid = self.getConfig("zoneid", section="dns")
            if record_set == None:
                record_set = self.getConfig("record_set", section="dns")
            
            logger.info(f"zoneid={zoneid} record_set={record_set} old_ip={self.my_ip} current_ip={my_public_ip} force_update={force_update}")
            self.my_ip = my_public_ip
            client = boto3.client("route53", aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
            response = client.change_resource_record_sets(
                HostedZoneId=zoneid,
                ChangeBatch={
                    "Comment": f"Changed record={record_set} old_ip={self.my_ip} current_ip={my_public_ip}",
                    "Changes": [
                        {
                            "Action": "UPSERT",
                            "ResourceRecordSet": {
                                "ResourceRecords": [{"Value": my_public_ip}],
                                "Name": record_set,
                                "Type": "A",
                                "TTL": ttl,
                            },
                        }
                    ],
                },
            )
            self._update_config("dns", "public_ip", my_public_ip)
        logger.info(f"current_public_ip={my_public_ip}")
        self.publish_mqtt(record_set, my_public_ip)
        return my_public_ip

    def publish_mqtt(self, item_name, payload):
        mqtt_server = self.getConfig("MQTT_SERVER", section="mqtt")
        mqtt_topic = self.getConfig("MQTT_TOPIC", section="mnqtt")
        if mqtt_server != None:
            logger.info(f"Publish mqtt item={item_name} payload={payload}")
            client1=paho.Client("mqtt_icloud")
            client1.on_publish = self._on_publish_mqtt
            try:
                client1.connect(mqtt_server)
                client1.publish(f"{mqtt_topic}/{item_name}/state",str(payload)) 
            except Exception as e:
                logger.warning("Exception " + str(e))
                return False
        return True

    def getConfig(self, key, section="settings"):
        config_file = self.config_file
        value = None
        if os.path.exists(config_file):
            config = configparser.ConfigParser(allow_no_value=True)
            config.read(config_file)
            if section in config and key in config[section]:
                value = config[section][key]
            else:
                value = os.environ.get(key)
        else:
            value = os.environ.get(key)
            logger.info(f"Creating initial version of the configuration file {config_file}")
            AWS_ACCESS_KEY_ID = input("Enter AWS_ACCESS_KEY_ID: ")
            AWS_ACCESS_KEY_ID = self.encode_value(AWS_ACCESS_KEY_ID)
            AWS_SECRET_ACCESS_KEY = input("Enter AWS_SECRET_ACCESS_KEY: ")
            AWS_SECRET_ACCESS_KEY = self.encode_value(AWS_SECRET_ACCESS_KEY)
            zoneid = input("Enter zoneid: ")
            record_set = input("Enter record_set: ")
            my_public_ip = self.get_my_public_ip()

            TEMPLATE = f"""
    [aws]
    AWS_ACCESS_KEY_ID = {AWS_ACCESS_KEY_ID}
    AWS_SECRET_ACCESS_KEY = {AWS_SECRET_ACCESS_KEY}
    [dns]
    zoneid = {zoneid}
    record_set = {record_set}
    ttl = 600
    public_ip = {my_public_ip}
    [mqtt]
    ;MQTT_SERVER = 127.0.0.1
    ;MQTT_TOPIC = pyroute53myip
    [scheduler]
    frequency = 60
            """
            with open(config_file, "w") as myfile:
                myfile.writelines(TEMPLATE)
        if value == None and key == "frequency":
            value = "60"
        if value == None and key == "ttl":
            value = "600"
        if value == None and key == "MQTT_TOPIC":
            value = "pyroute53myip"
        if "_key" in key.lower() and value != None and not value.startswith("(ENC)"):
            logger.info(f"Masquerade value for key {key}")
            value = self.encode_value(value)
            with open(config_file, "w") as myfile:
                config[section][key] = value
                config.write(myfile)
        value = self.decode_value(value)
        return value

    def encode_value(self, value):
        if value != None and not value.startswith("(ENC)"):
            master_key = socket.gethostname()
            #my_value = base64.b64encode(value.encode()).decode()
            my_value = encrypt_string(value, master_key)
            encoded_string = f"(ENC){my_value}"
        else:
            encoedd_string = value
        return encoded_string 

    def decode_value(self, value):
        if value != None and value.startswith("(ENC)"):
            master_key = socket.gethostname()
            value = value.replace("(ENC)", "")
            decoded_string = decrypt_string(value, master_key)
            #decoded_string = base64.b64decode(value.encode()).decode()
        else:
            decoded_string = value
        return decoded_string

    def _query_records(self, record, mode="a"):
        result = self.my_resolver.query(record, mode)
        all_records = []
        for item in result:
            all_records.append(item.to_text())
        return all_records
    
    def _update_config(self, section, key, value):
        config = configparser.ConfigParser()
        config.read(self.config_file)
        config.set(section, key, value)
        with open(self.config_file, 'w') as configfile:
            config.write(configfile)
        logger.info(f"Updated config={self.config_file} section={section} key={key} value={value}")

    def _on_publish_mqtt(self, client,userdata,result): 
        logger.debug("data published \n")
        pass

def main():
    logger.debug("Main")
    ZONEID = os.getenv("ZONEID")
    RECORDSET = os.getenv("RECORDSET")
    mytask = Pyroute53myip()
    #my_public_ip = mytask.update_my_public_ip(ZONEID, RECORDSET, force_update=True)
    my_public_ip = mytask.update_my_public_ip(ZONEID, RECORDSET, force_update=True)
    mytask.schedule_daemon()
    logger.info("Done")


if __name__ == "__main__":
    main()
