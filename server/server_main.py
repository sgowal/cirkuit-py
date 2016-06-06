import argparse
import core
import engine


def Run(args):
  server = core.Server(args.root, host=args.host, port=args.port)
  if args.circuit_directory:
    engine.Circuit.SetPath(args.circuit_directory)
  server.Start()


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--root", metavar='DIRECTORY', type=str, required=True, help="The root directory where the client files are located.")
  parser.add_argument("--circuit_directory", metavar='DIRECTORY', type=str, required=False, help="The directory where the circuit files are located.")
  parser.add_argument("--host", metavar='IP', type=str, default='localhost', help="The server hostname.")
  parser.add_argument("--port", metavar='PORT', type=int, default=8080, help="The server port.")
  Run(parser.parse_args())
