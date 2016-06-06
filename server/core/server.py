import BaseHTTPServer
import SocketServer
import cgi
import json
import os
import urlparse

import game
import game_listing
import engine
import user_listing

_MAX_PLAYERS_ALLOWED = 4

_ERROR_USERNAME_EXISTS_ALREADY = 1
_ERROR_GAME_FULL = 2
_ERROR_NOT_OWNER = 4
_ERROR_NOT_PLAYING = 5
_ERROR_NOT_STARTED = 6
_ERROR_WRONG_PARAMETERS = 7


class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

  def __init__(self, server_handle, *args, **kwargs):
    self.server_handle = server_handle
    BaseHTTPServer.BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

  def do_GET(self):
    parsed_url = urlparse.urlparse(self.path)
    path = parsed_url.path
    params = urlparse.parse_qs(parsed_url.query)
    # Main page.
    if path in self.server_handle.content:
      # Default header.
      self.send_response(200)
      self.send_header('Content-type', self.server_handle.content_type[path])
      self.end_headers()
      self.wfile.write(self.server_handle.content[path])
      self.wfile.close()
      return

    # Ajax requests (all JSON).
    # Using a large try block as the error message are the same for the same exception.
    try:
      # If there is user id in the parameters, refresh the last contact time.
      if 'user' in params:
        self.server_handle.GetUserListing().Refresh(params['user'][0])
      if 'game' in params:
        self.server_handle.GetGameListing().Refresh(params['game'][0])
      # Garbage collect users and games.
      self.server_handle.GetUserListing().GarbageCollect()
      self.server_handle.GetGameListing().GarbageCollect()

      if path == '/register':
        # Generate user.
        user = self.server_handle.GetUserListing().New(cgi.escape(params['username'][0]))
        self.AnswerJSON(200, {'user': user.id})

      elif path == '/list_games':
        # Verify the user (KeyError is raised if the user does not exist).
        self.server_handle.GetUserListing().Get(params['user'][0])
        self.AnswerJSON(200, self.server_handle.GetGameListing().JSONData())

      elif path == '/list_circuits':
        self.AnswerJSON(200, engine.Circuit.CircuitNames())

      elif path == '/create_game':
        # TODO: fix bug when unknown user creates a game (server freezes - likely deadlock).
        # Grab player name and number of players.
        max_players = int(params['max_players'][0])
        circuit_name = params['circuit_name'][0]
        if max_players > _MAX_PLAYERS_ALLOWED:
          raise ValueError()
        # Get user and create game.
        user = self.server_handle.GetUserListing().Get(params['user'][0])
        game_id = self.server_handle.GetGameListing().New(user, max_players, circuit_name).id
        self.AnswerJSON(200, {'game': game_id})

      elif path == '/join_game':
        game_id = params['game'][0]
        # Add user to game.
        user = self.server_handle.GetUserListing().Get(params['user'][0])
        self.server_handle.GetGameListing().AddPlayer(game_id, user)
        self.AnswerJSON(200, {'game': game_id})

      elif path == '/game_lobby':
        game_id = params['game'][0]
        game_instance = self.server_handle.GetGameListing().Get(game_id)
        self.AnswerJSON(200, game_instance.JSONData())

      elif path == '/start_game':
        game_id = params['game'][0]
        game_instance = self.server_handle.GetGameListing().Get(game_id)
        game_instance.FillWithComputerPlayers(authentication_id=params['user'][0], computer_ai=params['computer'][0])
        self.AnswerJSON(200, None)

      elif path == '/list_ai':
        self.AnswerJSON(200, engine.ListComputerPlayers())

      elif path == '/circuit_data':
        game_id = params['game'][0]
        game_instance = self.server_handle.GetGameListing().Get(game_id)
        self.AnswerJSON(200, game_instance.CircuitJSONData())

      elif path == '/race_status':
        game_id = params['game'][0]
        game_instance = self.server_handle.GetGameListing().Get(game_id)
        self.AnswerJSON(200, game_instance.RaceJSONData(authentication_id=params['user'][0]))

      elif path == '/move':
        game_id = params['game'][0]
        game_instance = self.server_handle.GetGameListing().Get(game_id)
        self.AnswerJSON(200, game_instance.Play(int(params['move'][0]), authentication_id=params['user'][0]))

      elif path == '/quit_game':
        game_instance = self.server_handle.GetGameListing().Get(params['game'][0])
        game_instance.RemovePlayer(authentication_id=params['user'][0])
        self.AnswerJSON(200, None)

      elif path == '/logout':
        self.server_handle.user_listing.Remove(params['user'][0])
        self.AnswerJSON(200, None)

      else:
        raise ValueError()

    except (ValueError, KeyError):
      self.AnswerJSON(400, _ERROR_WRONG_PARAMETERS)
    except user_listing.UsernameExistsError:
      self.AnswerJSON(400, _ERROR_USERNAME_EXISTS_ALREADY)
    except game.GameFullError:
      self.AnswerJSON(400, _ERROR_GAME_FULL)
    except game.NotCreatorError:
      self.AnswerJSON(400, _ERROR_NOT_OWNER)
    except game.NotStartedError:
      self.AnswerJSON(400, _ERROR_NOT_STARTED)
    except engine.HumanNotPlayingError:
      self.AnswerJSON(400, _ERROR_NOT_PLAYING)
    finally:
      # End close.
      self.wfile.close()

  def AnswerJSON(self, code, data):
    self.send_response(code)
    self.send_header('Content-type', 'text/json')
    self.end_headers()
    self.wfile.write(json.dumps(data))
    self.wfile.close()


def CreateHandler(server_handle):
  return lambda *args, **kwargs: RequestHandler(server_handle, *args, **kwargs)


class ThreadedHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
  """Handle requests in a separate thread."""


class Server(object):

  def __init__(self, directory, host='localhost', port=8080):
    self.host = host
    self.port = port
    # Load all content in memory.
    self.content = {}
    self.content_type = {}
    with open(os.path.join(directory, 'index.html')) as fp:
      self.content['/'] = fp.read()
      self.content_type['/'] = 'text/html'
    with open(os.path.join(directory, 'style.css')) as fp:
      self.content['/style.css'] = fp.read()
      self.content_type['/style.css'] = 'text/css'
    with open(os.path.join(directory, 'engine.js')) as fp:
      self.content['/engine.js'] = fp.read()
      self.content_type['/engine.js'] = 'text/javascript'
    with open(os.path.join(directory, 'loading.gif')) as fp:
      self.content['/loading.gif'] = fp.read()
      self.content_type['/loading.gif'] = 'image/gif'
    with open(os.path.join(directory, 'arrowdown.gif')) as fp:
      self.content['/arrowdown.gif'] = fp.read()
      self.content_type['/arrowdown.gif'] = 'image/gif'
    with open(os.path.join(directory, 'disconnected.png')) as fp:
      self.content['/disconnected.png'] = fp.read()
      self.content_type['/disconnected.png'] = 'image/png'
    with open(os.path.join(directory, 'favicon.ico')) as fp:
      self.content['/favicon.ico'] = fp.read()
      self.content_type['/favicon.ico'] = 'image/gif'
    with open(os.path.join(directory, 'jquery.mobile-events.min.js')) as fp:
      self.content['/jquery.mobile-events.min.js'] = fp.read()
      self.content_type['/jquery.mobile-events.min.js'] = 'text/javascript'

    # Start the game listing.
    self.game_listing = game_listing.GameListing()
    self.user_listing = user_listing.UserListing()

  def Start(self):
    try:
      server = ThreadedHTTPServer((self.host, self.port), CreateHandler(self))
      print 'Server started: http://%s:%d.' % (self.host, self.port)
      server.serve_forever()
    except KeyboardInterrupt:
      print 'Shutting down server.'
      self.game_listing.Stop()
      server.socket.close()

  def GetGameListing(self):
    return self.game_listing

  def GetUserListing(self):
    return self.user_listing
