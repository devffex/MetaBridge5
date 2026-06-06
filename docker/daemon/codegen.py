import os
import sys
from grpc_tools import protoc

def generate_stubs():
    print("Generating gRPC Python stubs...")
    proto_dir = os.path.join(os.path.dirname(__file__), 'protos')
    proto_file = os.path.join(proto_dir, 'terminal.proto')
    output_dir = os.path.dirname(__file__)
    
    # Run protoc command programmatically
    args = [
        'grpc_tools.protoc',
        f'-I{proto_dir}',
        f'--python_out={output_dir}',
        f'--grpc_python_out={output_dir}',
        proto_file
    ]
    
    status = protoc.main(args)
    if status == 0:
        print("gRPC Python stubs generated successfully.")
    else:
        print(f"Error: codegen failed with status code {status}")
        sys.exit(status)

if __name__ == '__main__':
    generate_stubs()
