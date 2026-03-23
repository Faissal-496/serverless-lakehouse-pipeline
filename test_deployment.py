#!/usr/bin/env python3
"""
Test connectivity to all deployed services
Tests: Jenkins, Airflow, RDS, RabbitMQ, S3
"""

import sys
import time
import json
import requests
from urllib.parse import urljoin

# Service endpoints
JENKINS_URL = "http://lakehouse-assura-jenkins-alb-617250655.eu-west-3.elb.amazonaws.com:8080"
AIRFLOW_URL = "http://lakehouse-assura-airflow-alb-421703647.eu-west-3.elb.amazonaws.com:8080"
RDS_HOST = "lakehouse-assurance-prod-postgres.c56eeys0i59p.eu-west-3.rds.amazonaws.com"
RDS_PORT = 5432
RDS_USER = "postgres"
RDS_DB = "lakehouse_prod"
RABBITMQ_HOST = "b-b7e21573-f118-4faf-a07b-b19d65bd5637.mq.eu-west-3.on.aws"
RABBITMQ_PORT = 5671
S3_BUCKET = "lakehouse-assurance-moto-prod"
AWS_REGION = "eu-west-3"

# Color codes
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

results = {
    "jenkins": False,
    "airflow": False,
    "rds": False,
    "rabbitmq": False,
    "s3": False,
}

def print_header(text):
    print(f"\n{BOLD}{BLUE}{'='*60}{RESET}")
    print(f"{BOLD}{BLUE}{text}{RESET}")
    print(f"{BOLD}{BLUE}{'='*60}{RESET}\n")

def print_success(msg):
    print(f"{GREEN}✓ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}✗ {msg}{RESET}")

def print_info(msg):
    print(f"{YELLOW}ℹ {msg}{RESET}")

def test_jenkins():
    """Test Jenkins HTTP endpoint"""
    print_header("Testing Jenkins")
    try:
        print_info(f"URL: {JENKINS_URL}")
        response = requests.get(f"{JENKINS_URL}/api/json", timeout=10)
        if response.status_code == 200:
            print_success("Jenkins API responded")
            data = response.json()
            print_info(f"Jenkins Version: {data.get('version', 'N/A')}")
            results["jenkins"] = True
        else:
            print_error(f"Jenkins returned status {response.status_code}")
    except requests.exceptions.Timeout:
        print_error("Jenkins request timed out (service may still be initializing)")
    except requests.exceptions.ConnectionError as e:
        print_error(f"Cannot connect to Jenkins: {e}")
    except Exception as e:
        print_error(f"Jenkins test failed: {e}")

def test_airflow():
    """Test Airflow HTTP endpoint"""
    print_header("Testing Airflow")
    try:
        print_info(f"URL: {AIRFLOW_URL}")
        response = requests.get(f"{AIRFLOW_URL}/health", timeout=10)
        if response.status_code == 200:
            print_success("Airflow health check passed")
            results["airflow"] = True
        else:
            print_error(f"Airflow returned status {response.status_code}")
    except requests.exceptions.Timeout:
        print_error("Airflow request timed out (service may still be initializing)")
    except requests.exceptions.ConnectionError as e:
        print_error(f"Cannot connect to Airflow: {e}")
    except Exception as e:
        print_error(f"Airflow test failed: {e}")

def test_rds():
    """Test PostgreSQL RDS connection"""
    print_header("Testing PostgreSQL RDS")
    try:
        import psycopg2
        from psycopg2 import OperationalError
        
        print_info(f"Endpoint: {RDS_HOST}:{RDS_PORT}")
        print_info(f"Database: {RDS_DB}")
        
        # Try to read RDS password from credentials file
        try:
            with open("les_credentials.txt", "r") as f:
                for line in f:
                    if line.startswith("RDS_MASTER_PASSWORD="):
                        rds_password = line.split("=")[1].strip()
                        break
        except Exception as e:
            print_error(f"Could not read RDS password: {e}")
            return
        
        conn = psycopg2.connect(
            host=RDS_HOST,
            port=RDS_PORT,
            database="postgres",  # Connect to default postgres DB first
            user=RDS_USER,
            password=rds_password,
            connect_timeout=10
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print_success(f"Connected to PostgreSQL: {version}")
        
        # Check if lakehouse_prod database exists
        cursor.execute("SELECT datname FROM pg_database WHERE datname = 'lakehouse_prod';")
        if cursor.fetchone():
            print_success("Database 'lakehouse_prod' exists")
        else:
            print_info("Database 'lakehouse_prod' does not exist (will be created by Airflow DAGs)")
        
        cursor.close()
        conn.close()
        results["rds"] = True
        
    except ImportError:
        print_error("psycopg2 not installed. Run: pip install psycopg2-binary")
    except Exception as e:
        print_error(f"RDS connection failed: {e}")

def test_rabbitmq():
    """Test RabbitMQ connection"""
    print_header("Testing RabbitMQ")
    try:
        import pika
        import ssl
        
        print_info(f"Endpoint: {RABBITMQ_HOST}:{RABBITMQ_PORT}")
        
        # Try to read RabbitMQ password from credentials file
        try:
            with open("les_credentials.txt", "r") as f:
                for line in f:
                    if line.startswith("MQ_PASSWORD="):
                        mq_password = line.split("=")[1].strip()
                        break
        except Exception as e:
            print_error(f"Could not read MQ password: {e}")
            return
        
        # Create SSL context
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        credentials = pika.PlainCredentials("rabbituser", mq_password)
        parameters = pika.ConnectionParameters(
            host=RABBITMQ_HOST,
            port=RABBITMQ_PORT,
            credentials=credentials,
            ssl_options=pika.SSLOptions(ssl_context),
            connection_attempts=3,
            retry_delay=2,
            socket_timeout=10
        )
        
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        print_success("Connected to RabbitMQ")
        
        # Check RabbitMQ version
        connection.close()
        results["rabbitmq"] = True
        
    except ImportError:
        print_error("pika not installed. Run: pip install pika")
    except Exception as e:
        print_error(f"RabbitMQ connection failed: {e}")

def test_s3():
    """Test S3 bucket access"""
    print_header("Testing S3 Data Lake")
    try:
        import boto3
        from botocore.exceptions import ClientError
        
        print_info(f"Bucket: {S3_BUCKET}")
        print_info(f"Region: {AWS_REGION}")
        
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        
        # Test bucket exists and is accessible
        try:
            response = s3_client.head_bucket(Bucket=S3_BUCKET)
            print_success(f"S3 bucket '{S3_BUCKET}' is accessible")
            
            # List objects
            response = s3_client.list_objects_v2(Bucket=S3_BUCKET, MaxKeys=5)
            object_count = response.get("KeyCount", 0)
            print_info(f"Objects in bucket: {object_count}")
            
            # Check for lake structure
            prefixes = ["bronze/", "silver/", "gold/"]
            for prefix in prefixes:
                try:
                    response = s3_client.head_object(Bucket=S3_BUCKET, Key=prefix)
                    print_info(f"  └─ /{prefix} exists")
                except ClientError:
                    print_info(f"  └─ /{prefix} does not exist (will be created by ETL)")
            
            results["s3"] = True
            
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                print_error(f"Bucket '{S3_BUCKET}' does not exist")
            else:
                print_error(f"S3 access error: {e}")
    
    except ImportError:
        print_error("boto3 not installed. Run: pip install boto3")
    except Exception as e:
        print_error(f"S3 test failed: {e}")

def main():
    print(f"\n{BOLD}{BLUE}Lakehouse Deployment Health Check{RESET}")
    print(f"{BLUE}Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}{RESET}\n")
    
    # Test all services
    test_jenkins()
    test_airflow()
    test_rds()
    test_rabbitmq()
    test_s3()
    
    # Summary
    print_header("Health Check Summary")
    
    passed = sum(results.values())
    total = len(results)
    
    for service, status in results.items():
        status_str = f"{GREEN}✓ PASS{RESET}" if status else f"{RED}✗ FAIL{RESET}"
        print(f"  {service.upper():15} {status_str}")
    
    print(f"\n{BOLD}Result: {passed}/{total} services operational{RESET}")
    
    if passed == total:
        print(f"\n{GREEN}{BOLD}✓ ALL SERVICES OPERATIONAL - Ready for Phase 5{RESET}\n")
        return 0
    elif passed >= 3:
        print(f"\n{YELLOW}{BOLD}⚠ PARTIAL SUCCESS - Some services initializing or unreachable{RESET}")
        print(f"{YELLOW}This may be normal if services are still starting up.{RESET}\n")
        return 1
    else:
        print(f"\n{RED}{BOLD}✗ CRITICAL ISSUES - Multiple services offline{RESET}\n")
        return 2

if __name__ == "__main__":
    sys.exit(main())
