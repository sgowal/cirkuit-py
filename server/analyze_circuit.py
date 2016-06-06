import argparse
import engine


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--circuit_directory", metavar='DIRECTORY', type=str, required=False, help="The directory where the circuit files are located.")
  parser.add_argument("--circuit_name", metavar='NAME', type=str, required=True, help="The name of the circuit to analyze.")
  parser.add_argument("--plot", type=bool, default=True, help="Whether to plot the analysis.")
  args = parser.parse_args()
  if args.circuit_directory:
    engine.Circuit.SetPath(args.circuit_directory)
  engine.GetAnalyzer(args.circuit_name, plot=args.plot)
