import sys
import os
import grpc

# Add stubs folder to path if run locally or in docker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import terminal_pb2
import terminal_pb2_grpc

def test(server_address: str = 'localhost:50051'):
    print(f"Connecting to gRPC server at {server_address}...")
    with grpc.insecure_channel(server_address) as channel:
        stub = terminal_pb2_grpc.TerminalServiceStub(channel)
        
        # Test Health Check
        print("Sending GetHealth request...")
        health = stub.GetHealth(terminal_pb2.HealthRequest())
        print(f"GetHealth success: status='{health.status}', service='{health.service}'")
        
        # Test Terminal Info
        print("Sending GetTerminalInfo request...")
        info = stub.GetTerminalInfo(terminal_pb2.InfoRequest())
        print(f"GetTerminalInfo success: connected={info.connected}, build={info.build}")

        # Test Account Info
        print("Sending GetAccountInfo request...")
        acct = stub.GetAccountInfo(terminal_pb2.InfoRequest())
        print(f"GetAccountInfo success: login={acct.login}, balance={acct.balance}, currency='{acct.currency}', company='{acct.company}'")

if __name__ == '__main__':
    addr = sys.argv[1] if len(sys.argv) > 1 else 'localhost:50051'
    test(addr)
