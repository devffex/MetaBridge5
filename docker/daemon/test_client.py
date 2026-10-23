import sys
import os
import grpc

# Add stubs folder to path if run locally or in docker
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import terminal_pb2
import terminal_pb2_grpc


def test(server_address: str = "localhost:50051"):
    print(f"Connecting to gRPC server at {server_address}...")
    
    # Retrieve api key from environment or use test fallback
    api_key = os.environ.get("METABRIDGE5_API_KEY", "test-api-key")
    metadata = [("x-api-key", api_key)]
    
    with grpc.insecure_channel(server_address) as channel:
        stub = terminal_pb2_grpc.TerminalServiceStub(channel)

        # 1. Test Health Check (should bypass authentication check)
        print("Sending GetHealth request (public)...")
        health = stub.GetHealth(terminal_pb2.HealthRequest())
        print(
            f"GetHealth success: status='{health.status}', service='{health.service}'"
        )

        # 2. Test Terminal Info (authenticated)
        print("Sending GetTerminalInfo request...")
        info = stub.GetTerminalInfo(terminal_pb2.InfoRequest(), metadata=metadata)
        print(
            f"GetTerminalInfo success: connected={info.connected}, build={info.build}"
        )

        # 3. Test Account Info (authenticated)
        print("Sending GetAccountInfo request...")
        acct = stub.GetAccountInfo(terminal_pb2.InfoRequest(), metadata=metadata)
        print(
            f"GetAccountInfo success: login={acct.login}, balance={acct.balance}, currency='{acct.currency}', company='{acct.company}'"
        )

        # 4. Test GetTerminalStatus (authenticated)
        print("Sending GetTerminalStatus request...")
        status_resp = stub.GetTerminalStatus(terminal_pb2.TerminalStatusRequest(), metadata=metadata)
        print(
            f"GetTerminalStatus success: status='{status_resp.status}', pid={status_resp.pid}, cpu_percent={status_resp.cpu_percent}%, memory_rss_mb={status_resp.memory_rss_mb}MB"
        )

        # 5. Test DeployAsset (authenticated)
        print("Sending DeployAsset request...")
        asset_content = b"// Test Expert Advisor\nvoid OnTick() {}"
        deploy_resp = stub.DeployAsset(
            terminal_pb2.DeployAssetRequest(
                asset_type="ea",
                file_name="TestEA.mq5",
                file_content=asset_content
            ),
            metadata=metadata
        )
        print(
            f"DeployAsset success: success={deploy_resp.success}, destination='{deploy_resp.destination}', error='{deploy_resp.error}'"
        )

        # 6. Test GetTerminalLogs (authenticated)
        print("Sending GetTerminalLogs request...")
        try:
            logs_resp = stub.GetTerminalLogs(
                terminal_pb2.TerminalLogsRequest(lines=10),
                metadata=metadata
            )
            print(
                f"GetTerminalLogs success: file='{logs_resp.file}', total_lines={logs_resp.total_lines}, returned_lines={logs_resp.returned_lines}"
            )
            print("Logs sample:")
            for line in logs_resp.content:
                print(f"  {line}")
        except grpc.RpcError as e:
            if e.code() == grpc.StatusCode.NOT_FOUND:
                print("GetTerminalLogs: logs directory/files not found (expected if MT5 has never started)")
            else:
                raise

        # 7. Test StopTerminal (authenticated)
        print("Sending StopTerminal request...")
        stop_resp = stub.StopTerminal(terminal_pb2.StopTerminalRequest(), metadata=metadata)
        print(f"StopTerminal success: success={stop_resp.success}")

        # 8. Test StartTerminal (authenticated)
        print("Sending StartTerminal request...")
        start_resp = stub.StartTerminal(terminal_pb2.StartTerminalRequest(), metadata=metadata)
        print(f"StartTerminal success: success={start_resp.success}")


if __name__ == "__main__":
    addr = sys.argv[1] if len(sys.argv) > 1 else "localhost:50051"
    test(addr)
