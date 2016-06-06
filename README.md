# CirKuit 2D - Python Edition

This project takes over the defunct CirKuit 2D project (written in Java).
It is now built from the ground up to allow multi-player races using Javascript (on the client side) and Python (on the server side).

## Starting a server (for local play)

```bash
cd server
python server_main.py --port 8080 --root ../client --circuit_directory ../circuits
```

## Connecting to the server and playing against the AI

1. Open Chrome (or your favorite browser)
2. Navigate to http://localhost:8080
3. Enter a username and click register
4. Create a new game
  1. Select the number of players (that includes you)
  2. Select the race track
  3. Click create
5. Select a computer player (recommended is AStarPlayer)
6. Start the game

## Starting a server (for remote play with friend)

Make sure your router is setup with port forwarding to the machine that will run the
CirKuit server. We will assume the forwarding port to be 12345 and the IP address of your
machine on the local network to be 192.168.0.2.

```bash
cd server
python server_main.py --port 12345 --host 192.168.0.2 --root ../client --circuit_directory ../circuits
```

## Play with a remote friend

1. Open Chrome (or your favorite browser)
2. Navigate to http://192.168.0.2:12345
3. Enter a username and click register
4. Create a new game
  1. Select the number of players (that includes you)
  2. Select the race track
  3. Click create
5. Go on Google and type "my ip". Google will return your external IP address (e.g., 77.52.104.123)
6. Tell your friend to open their browser and navigate to http://77.52.104.123:12345
7. They need to enter a username and they should be able to see that there is a ongoing game
8. They can now join that game
9. And you can click start

## Screenshots

### Welcome screen

![Welcome screen](https://raw.githubusercontent.com/sgowal/cirkuit-py/master/doc/screenshot_00.png)

### Game lobby

![Game lobby](https://raw.githubusercontent.com/sgowal/cirkuit-py/master/doc/screenshot_01.png)

### Race

![Race](https://raw.githubusercontent.com/sgowal/cirkuit-py/master/doc/screenshot_02.png)
