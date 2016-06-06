var COLORS = ["#1E90FF", "#DC143C", "#90EE90", "#FFC0CB"];
var NUMBERS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "9th", "10th", "11th", "12th"];
var MOVE_STATUS_COLORS = ["#228B22", "#FF0000", "#7FFF00"];
var STATUS_TEXT = ["RUNNING", "CRASHED", "FINISHED", "DISCONNECTED"];
var MAX_SECONDS_TO_PLAY = 60;
var TOUCH_OFFSET = document.getElementById('measurement').offsetHeight * 0.6;

var listing_game_timeout = null;
var lobby_info_timeout = null;
var race_status_timeout = null;
var play_move_timeout = null;
var user = null;
var game = null;
var is_creator = null;
var available_moves = null;
var player_positions = null;
var player_name = null;
var player_round = null;
var previously_received_player_round = -1;
var num_players = 4;

var circuit_inner_border = null;
var circuit_name = null;
var circuit_grid_size = null;
var circuit_maximum_speed = null;
var circuit_starting_line = null;
var circuit_outer_border = null;

var prerender_canvas = null;
var game_canvas = null;
var game_canvas_ctx = null;

var mouse_position_x = 0;
var mouse_position_y = 0;
var previously_drawn_closest = null;
var previously_drawn_available_moves = null;
var previously_drawn_player_positions = null;
var player_colors = null;
var seconds_left_to_play = MAX_SECONDS_TO_PLAY;

var prevent_double_click = false;

var fingerdown = false;
var fingerdown_start = false;
var fingerdown_x = 0;
var fingerdown_y = 0;
var fingerdown_timeout = null;
var fingerdown_closest_index = null;

///////////////////////
// Drawing function. //
///////////////////////

function drawPolygon(ctx, points, closed, color) {
  ctx.beginPath();
  ctx.lineWidth = "2";
  ctx.strokeStyle = color;
  var start = 2;
  if (closed) {
    start = 0;
    ctx.moveTo(points[points.length - 2], points[points.length - 1]);
  } else {
    ctx.moveTo(points[0], points[1]);
  }
  for (var i = start; i < points.length; i += 2) {
    ctx.lineTo(points[i], points[i + 1]);
  }
  ctx.stroke();
}

function drawPlayer(ctx, posx, posy, border_color, color) {
  ctx.beginPath();
  ctx.lineWidth = 2;
  ctx.strokeStyle = border_color;
  if (fingerdown) {
    ctx.arc(posx, posy, 4, 0, Math.PI*2, true);
  } else {
    ctx.arc(posx, posy, 3, 0, Math.PI*2, true);
  }
  ctx.closePath();
  ctx.stroke();
  ctx.fillStyle = color;
  ctx.fill();
}

function clearPlayer(ctx, posx, posy) {
  ctx.clearRect(posx - 4, posy - 4, posx + 4, posy + 4);
}

function drawArrow(ctx, fromx, fromy, tox, toy, color){
    var headlen = 5;
    var angle = Math.atan2(toy-fromy,tox-fromx);
    ctx.beginPath();
    ctx.moveTo(fromx, fromy);
    ctx.lineTo(tox, toy);
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(tox, toy);
    ctx.lineTo(tox-headlen*Math.cos(angle-Math.PI/7),toy-headlen*Math.sin(angle-Math.PI/7));
    ctx.lineTo(tox-headlen*Math.cos(angle+Math.PI/7),toy-headlen*Math.sin(angle+Math.PI/7));
    ctx.lineTo(tox, toy);
    ctx.lineTo(tox-headlen*Math.cos(angle-Math.PI/7),toy-headlen*Math.sin(angle-Math.PI/7));
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.fill();
}

function drawStartingLine(ctx, startingLine, color) {
  if (startingLine[0] == startingLine[2]) {
    if (startingLine[1] < startingLine[3]) {
      drawArrow(ctx, startingLine[0], startingLine[1], startingLine[0] - 20, startingLine[1], color);
    } else {
      drawArrow(ctx, startingLine[0], startingLine[1], startingLine[0] + 20, startingLine[1], color);
    }
  } else {
    if (startingLine[0] < startingLine[2]) {
      drawArrow(ctx, startingLine[0], startingLine[1], startingLine[0], startingLine[1] + 20, color);
    } else {
      drawArrow(ctx, startingLine[0], startingLine[1], startingLine[0], startingLine[1] - 20, color);
    }
  }
}

function drawGame(only_mouse_move) {
  // TODO: Make drawing efficient (avoid redrawing if not needed).
  // If only the mouse moved, we know that we only need to redraw the available points.
  var canvas_cleared = false;
  if (!only_mouse_move) {
    canvas_cleared = true;
    // Clear canvas.
    game_canvas_ctx.clearRect(0, 0, game_canvas.get(0).width, game_canvas.get(0).height);
    // Draw circuit.
    game_canvas_ctx.drawImage(prerender_canvas, 0, 0);
    // Draw players.
    if (player_positions !== null) {
      for (var name in player_positions) {
        var trajectory = player_positions[name];
        if (trajectory.length < 2) {
          continue;
        }
        game_canvas_ctx.beginPath();
        game_canvas_ctx.lineWidth = "2";
        game_canvas_ctx.strokeStyle = player_colors[name];
        game_canvas_ctx.moveTo(trajectory[0][0], trajectory[0][1]);
        for (var i = 1; i < trajectory.length; i++) {
          game_canvas_ctx.lineTo(trajectory[i][0], trajectory[i][1]);
        }
        game_canvas_ctx.stroke();
      }
      // Draw last position properly.
      for (var name in player_positions) {
        var trajectory = player_positions[name];
        if (trajectory.length === 0) {
          continue;
        }
        drawPlayer(game_canvas_ctx, trajectory[trajectory.length - 1][0], trajectory[trajectory.length - 1][1], "#333", player_colors[name]);
      }
    }
  }
  // Draw available moves if any.
  if (available_moves !== null && available_moves.length > 0) {
    var closest_index = GetClosestPoint(mouse_position_x, mouse_position_y);
    // Only redraw if the closest changed (or we cleared the canvas).
    if (closest_index != previously_drawn_closest || canvas_cleared) {
      for (var i = 0; i < available_moves.length; i++) {
        drawPlayer(game_canvas_ctx, available_moves[i].x, available_moves[i].y, "#333", "#FFD700");
      }
      drawPlayer(game_canvas_ctx, available_moves[closest_index].x, available_moves[closest_index].y, "#333", MOVE_STATUS_COLORS[available_moves[closest_index].status]);
      previously_drawn_closest = closest_index;
    }
  }
  // Set previously drawn.
  previously_drawn_available_moves = available_moves;
  previously_drawn_player_positions = player_positions;
}

function UpdatePlayerListing(rounds, status, laps, distance_left) {
  // Sort the names such the player with
  // - The highest lap count.
  // - The smallest distance left is first.
  // - The smallest round
  // is first.
  function Ordering(a, b) {
    if (laps[a] != laps[b]) {
      return laps[b] - laps[a];
    } else if (distance_left[a] != distance_left[b]) {
      return distance_left[a] - distance_left[b];
    }
    return rounds[a] - rounds[b];
  }

  var list = $('#game_play_players');
  list.empty();
  names = [];
  for (var name in rounds) {
    names.push(name);
  }
  names.sort(Ordering);
  // Check if someone is still running.
  var is_running = false;
  for (var i = 0; i < names.length; i++) {
    if (status[names[i]] == 0) {
      is_running = true;
      break;
    }
  }
  if (is_running) {
    for (var i = 0; i < names.length; i++) {
      var name = names[i];
      var status_text = " played " + rounds[name] + " rounds (" + NUMBERS[laps[name]] + " lap)";
      if (status[name] == 1) {  // Crash.
        status_text = " crashed";
      } else if (status[name] == 2) {
        status_text = " finished the race";
      } else if (status[name] == 3) {
        status_text = " was disconnected";
      }
      list.append('<li><font color="' + player_colors[name] + '"><b>' + name + '</b>' + status_text + '</li>');
    }
  } else {
    var previous_rank = -1;
    for (var i = 0; i < names.length; i++) {
      var name = names[i];
      var rank = i;
      if (i > 0) {
        if (Ordering(names[i], names[i - 1]) === 0) {
          rank = previous_rank;
        }
      }
      previous_rank = rank;
      var status_text = " finished in " + rounds[name].toFixed(2) + " rounds and placed " + NUMBERS[i];
      if (status[name] == 1) {
        status_text = " crashed and placed " + NUMBERS[i];
      } else if (status[name] == 3) {
        status_text = " was disconnected and placed " + NUMBERS[i];
      }
      list.append('<li><font color="' + player_colors[name] + '"><b>' + name + '</b>' + status_text + '</li>');
    }
  }

}

function Countdown() {
  seconds_left_to_play--;
  $("#game_play_status").html("It's your turn (" + seconds_left_to_play + ")...");
  if (seconds_left_to_play > 0) {
    play_move_timeout = window.setTimeout(Countdown, 1000);
  } else {
    seconds_left_to_play = MAX_SECONDS_TO_PLAY;
    LeaveGamePlayNonsafe();
  }
}

///////////////////////
// Input events.     //
///////////////////////

function Distance2(x1, y1, x2, y2) {
  var dx = x2 - x1;
  var dy = y2 - y1;
  return dx * dx + dy * dy;
}

function GetClosestPoint(x, y) {
  var closest_index = 0;
  var closest_dist = Distance2(x, y, available_moves[0].x, available_moves[0].y);
  for (var i = 1; i < available_moves.length; i++) {
    var dist = Distance2(x, y, available_moves[i].x, available_moves[i].y);
    if (dist < closest_dist) {
      closest_dist = dist;
      closest_index = i;
    }
  }
  return closest_index;
}

function CanvasMouseMoved(e) {
  var offset = game_canvas.offset();
  mouse_position_x = e.pageX - offset.left;
  mouse_position_y = e.pageY - offset.top;
  drawGame(true);
}

function CanvasMouseClicked(e) {
  var offset = game_canvas.offset();
  mouse_position_x = e.pageX - offset.left;
  mouse_position_y = e.pageY - offset.top;

  if (available_moves !== null && available_moves.length > 0) {
    var closest_index = GetClosestPoint(mouse_position_x, mouse_position_y);
    // Send move to server.
    RequestMove(closest_index);
    // Clear available moves and immediately update the player position
    // while waiting for the race_status request.
    player_positions[player_name].push([available_moves[closest_index].x, available_moves[closest_index].y]);
    available_moves = null;
    drawGame(false);
  }
}

function ValidateFingerdownIndex() {
  mouse_position_x = fingerdown_x;
  mouse_position_y = fingerdown_y - TOUCH_OFFSET;
  if (available_moves !== null && available_moves.length > 0) {
    var closest_index = GetClosestPoint(mouse_position_x, mouse_position_y);
    // Send move to server.
    RequestMove(closest_index);
    // Clear available moves and immediately update the player position
    // while waiting for the race_status request.
    player_positions[player_name].push([available_moves[closest_index].x, available_moves[closest_index].y]);
    available_moves = null;
    fingerdown = false;
    drawGame(false);
  }
}

function CanvasTapEnd(e) {
  if (fingerdown) {
    e.preventDefault();
    window.clearTimeout(fingerdown_timeout);
  }
  fingerdown = false;
}

function CanvasTapMove(e) {
  if (fingerdown) {
    e.preventDefault();
    var offset = game_canvas.offset();
    fingerdown_x = e.originalEvent.touches[0].pageX - offset.left;
    fingerdown_y = e.originalEvent.touches[0].pageY - offset.top;
    mouse_position_x = fingerdown_x;
    mouse_position_y = fingerdown_y - TOUCH_OFFSET;
    var new_fingerdown_closest_index = GetClosestPoint(mouse_position_x, mouse_position_y);
    if (new_fingerdown_closest_index != fingerdown_closest_index) {
      window.clearTimeout(fingerdown_timeout);
      fingerdown_timeout = window.setTimeout(ValidateFingerdownIndex, 1500);
      fingerdown_closest_index = new_fingerdown_closest_index;
    }
    drawGame(true);
  }
}

function CanvasTapHold(e) {
  fingerdown = true;
  var offset = game_canvas.offset();
  fingerdown_x = e.originalEvent.touches[0].pageX - offset.left;
  fingerdown_y = e.originalEvent.touches[0].pageY - offset.top;
  mouse_position_x = fingerdown_x;
  mouse_position_y = fingerdown_y - TOUCH_OFFSET;
  fingerdown_closest_index = GetClosestPoint(mouse_position_x, mouse_position_y);
  fingerdown_timeout = window.setTimeout(ValidateFingerdownIndex, 1500);
  e.preventDefault();
}

function ActivateTapHold() {
  if (fingerdown_start) {
    fingerdown = true;
  }
}

function DocumentScroll(e) {
  if (fingerdown) {
    e.preventDefault();
  }
}

///////////////////////
// JSON requests.    //
///////////////////////

function RegisterUser() {
  if (prevent_double_click) {
    return;
  }
  prevent_double_click = true;
  StartLoadingUI('Registering...');
  var username = $("#username").val();
  console.log('Trying to register username:' + username);
  var request = $.getJSON("/register", {
      username: username,
  });
  request.done(function(json) {
    console.log("Register success: " + json);
    user = json.user;
    player_name = username;
    SetupListingUI();
    StopLoadingUI();
    prevent_double_click = false;
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Register failed: " + textStatus + ", " + error);
    if (username.length === 0) {
      $("#username_error").html("Username not set.");
    } else {
      $("#username_error").html("Username is already in use.");
    }
    StopLoadingUI();
    prevent_double_click = false;
  });
}

function RequestAvailableGames() {
  // Asynchronous Ajax.
  var request = $.getJSON("/list_games", {
      user: user,  // This gurantees that the user is kept alive on the server side.
  });
  request.done(function(json) {
    console.log("Listing success: " + json);
    var table = $('#list_games_table_table');
    table.empty();
    if (json.length > 0) {
      table.append('<tr><td>Game ID</td><td>Creation date</td><td># Players</td><td>Maximum</td><td></td></tr>');
    }
    $.each(json, function(i, item) {
      table.append('<tr><td>' + item.id + '</td><td>' + item.creation + '</td>' +
                   '<td>' + item.num_players + '</td><td>' + item.max_players + '</td>' +
                   '<td></td></tr>');
      $(document.createElement('button'))
          .html('Join')
          .appendTo(table.find('td:last'))
          .click(function() { JoinGame(item.id); });
    });
    if (json.length === 0) {
      table.append('<tr><td>There are no ongoing games. Create one?</td></tr>');
    }
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Listing failed: " + textStatus + ", " + error);
    StartDisconnectedUI();
  });
  // Request available games in 10 seconds again.
  listing_game_timeout = window.setTimeout(RequestAvailableGames, 10000);
}

function RequestAvailableCircuitNames() {
  var request = $.getJSON("/list_circuits");
  request.done(function(json) {
    console.log("Circuit list success: " + json);
    var circuit_options = $('#circuit_name');
    circuit_options.empty();
    $.each(json, function(i, item) {
      circuit_options.append('<option value="' + item + '">' + item + '</option>');
    });
    if (json.length === 0) {
      circuit_options.append('<option value="Patatoid">Patatoid</option>');
    }
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Circuit list failed: " + textStatus + ", " + error);
  });
}

function CreateNewGame() {
  if (prevent_double_click) {
    return;
  }
  prevent_double_click = true;
  StartLoadingUI('Creating game...');
  var request = $.getJSON("/create_game", {
      user: user,
      max_players: $("#max_players").val(),
      circuit_name: $("#circuit_name").val(),
  });
  request.done(function(json) {
    console.log("Create success: " + json);
    game = json.game;
    is_creator = true;
    SetupGameLobbyUI();
    StopLoadingUI();
    prevent_double_click = false;
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Create failed: " + textStatus + ", " + error);
    StopLoadingUI();
    prevent_double_click = false;
  });
}

function JoinGame(identifier) {
  if (prevent_double_click) {
    return;
  }
  prevent_double_click = true;
  StartLoadingUI('Joining game...');
  console.log("Joining game: " + identifier);
  var request = $.getJSON("/join_game", {
      user: user,
      game: identifier,
  });
  request.done(function(json) {
    console.log("Join success: " + json);
    game = json.game;
    is_creator = false;
    SetupGameLobbyUI();
    StopLoadingUI();
    prevent_double_click = false;
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Join failed: " + textStatus + ", " + error);
    StopLoadingUI();
    prevent_double_click = false;
  });
}

function StartGame() {
  if (prevent_double_click) {
    return;
  }
  prevent_double_click = true;
  StartLoadingUI('Starting race...');
  var request = $.getJSON("/start_game", {
      game: game,
      user: user,
      computer: $("#computer_ai").val(),
  });
  request.done(function(json) {
    console.log("Start success: " + json);
    SetupGameUI();
    StopLoadingUI();
    prevent_double_click = false;
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Start failed: " + textStatus + ", " + error);
    StopLoadingUI();
    prevent_double_click = false;
  });
}

function RequestAvailableComputerAI() {
  var request = $.getJSON("/list_ai");
  request.done(function(json) {
    console.log("AI list success: " + json);
    var circuit_options = $('#computer_ai');
    circuit_options.empty();
    $.each(json, function(i, item) {
      circuit_options.append('<option value="' + item + '">' + item + '</option>');
    });
    if (json.length === 0) {
      circuit_options.append('<option value="AStarPlayer">AStarPlayer</option>');
    }
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "AI list failed: " + textStatus + ", " + error);
  });
}

function LeaveGameLobby() {
  if (prevent_double_click) {
    return;
  }
  prevent_double_click = true;
  var request = $.getJSON("/quit_game", {
      game: game,
      user: user,
  });
  request.done(function(json) {
    console.log("Quit game success: " + json);
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Quit game failed: " + textStatus + ", " + error);
  });
  SetupListingUI();
  prevent_double_click = false;
}

function RequestLobbyInfo() {
  var request = $.getJSON("/game_lobby", {
      game: game,
  });
  request.done(function(json) {
    console.log("Lobby success: " + json);
    $('#game_lobby_players').html(json.players.length + '/' + json.max_players);
    var list = $('#game_lobby_players');
    var news = $('#game_lobby_news');
    list.empty();
    news.empty();
    $.each(json.players, function(i, item) {
      list.append('<li><div class="player_name">' + item[0] + '</div></li>');
      news.append('<li>' + item + ' joined.</li>');
    });
    if (json.players.length == json.max_players) {
      SetupGameUI();
    }
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Lobby failed: " + textStatus + ", " + error);
  });
  // Request info in 2 seconds again.
  lobby_info_timeout = window.setTimeout(RequestLobbyInfo, 2000);
}

function RequestCircuitData() {
  var request = $.getJSON("/circuit_data", {
      game: game,
  });
  request.done(function(json) {
    console.log("Circuit success: " + json);
    circuit_inner_border = json.circuit_inner_border;
    circuit_name = json.circuit_name;
    circuit_grid_size = json.circuit_grid_size;
    circuit_starting_line = json.circuit_starting_line;
    circuit_outer_border = json.circuit_outer_border;

    $("#title").html(circuit_name + ' - laps: ' + json.num_laps);
    $("#game_play_status").html("Preparing game...");
    prerender_canvas = $("#prerender_canvas").get(0);
    var prerender_canvas_ctx = prerender_canvas.getContext('2d');
    prerender_canvas_ctx.clearRect(0, 0, prerender_canvas.width, prerender_canvas.height);
    drawPolygon(prerender_canvas_ctx, circuit_inner_border, true, "#333");
    drawPolygon(prerender_canvas_ctx, circuit_outer_border, true, "#333");
    drawPolygon(prerender_canvas_ctx, circuit_starting_line, false, "#333");
    drawStartingLine(prerender_canvas_ctx, circuit_starting_line, "#333");

    // Drawing variables.
    available_moves = null;
    player_positions = null;
    player_round = null;
    previously_received_player_round = -1;
    num_players = 4;
    player_colors = null;
    previously_drawn_closest = null;
    previously_drawn_available_moves = null;
    previously_drawn_player_positions = null;
    game_canvas_ctx = game_canvas.get(0).getContext("2d");
    $("#circuit_canvas").css("background-size", circuit_grid_size + "px " + circuit_grid_size + "px");
    $("#circuit_canvas").css("background-position", circuit_starting_line[0] + "px " + circuit_starting_line[1] + "px");
    drawGame(false);

    RequestRaceStatus();
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log("Circuit failed: " + textStatus + ", " + error);
  });
}

function LeaveGamePlayNonsafe() {
  var request = $.getJSON("/quit_game", {
      game: game,
      user: user,
  });
  request.done(function(json) {
    console.log("Quit game success: " + json);
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Quit game failed: " + textStatus + ", " + error);
  });
  SetupListingUI();
}

function LeaveGamePlay() {
  if (prevent_double_click) {
    return;
  }
  LeaveGamePlayNonsafe();
  prevent_double_click = false;
}

function RequestRaceStatus() {
  var request = $.getJSON("/race_status", {
      game: game,
      user: user
  });
  request.done(function(json) {
    console.log("Race status success: " + json);
    // Setup colors.
    if (player_colors === null) {
      player_colors = [];
      var i = 0;
      for (var name in json.rounds) {
        player_colors[name] = COLORS[i];
        i++;
      }
      num_players = i;
    }

    // If it's our turn, setup available moves.
    if (json.is_turn) {
      // Store which round I'm playing in order to not update anything in that case.
      player_round = json.rounds[player_name];
      // Only update UI once if it's the players turn the first time this is called.
      if (previously_received_player_round != player_round) {
        seconds_left_to_play = MAX_SECONDS_TO_PLAY;
        play_move_timeout = window.setTimeout(Countdown, 1000);
        $("#game_play_status").html("It's your turn (" + seconds_left_to_play + ")...");

        available_moves = json.moves;
        player_positions = json.positions;
        // Update UI (besides canvas).
        UpdatePlayerListing(json.rounds, json.status, json.laps, json.distance_left);
        previously_received_player_round = player_round;
      }
    } else {
      if (play_move_timeout !== null) {
        window.clearTimeout(play_move_timeout);
      }
      var extra_comment = "";
      if (json.status[player_name] == 1 /* crashed */) {
        extra_comment = "You've crashed :( &ndash; ";
      } else if (json.status[player_name] == 2 /* finished */) {
        extra_comment = "You're done :) &ndash; ";
      }
      if (json.playing_now === null) {
        $("#game_play_status").html(extra_comment + "The race is over.");
      } else {
        $("#game_play_status").html(extra_comment + "Waiting for " + json.playing_now + "...");
      }
      available_moves = null;
      player_positions = json.positions;
      // Update UI (besides canvas).
      UpdatePlayerListing(json.rounds, json.status, json.laps, json.distance_left);
    }

    // Redraw.
    drawGame(false);
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Race status failed: " + textStatus + ", " + error);
  });
  // Request status in 2 seconds again.
  race_status_timeout = window.setTimeout(RequestRaceStatus, 500 * num_players);
}

function RequestMove(move_index) {
  if (prevent_double_click) {
    return;
  }
  prevent_double_click = true;
  var request = $.getJSON("/move", {
      game: game,
      user: user,
      move: move_index,
  });
  request.done(function(json) {
    console.log("Move success: " + json);
    if (play_move_timeout !== null) {
      window.clearTimeout(play_move_timeout);
    }
  });
  request.fail(function(jqxhr, textStatus, error) {
    console.log( "Move failed: " + textStatus + ", " + error);
  });
  prevent_double_click = false;
}

///////////////////////
// UI Setup.         //
///////////////////////

function StartDisconnectedUI(text) {
  $("#reload_page").click(function() {
    location.reload();
  });
  $("#overlay_disconnected").show();
}

function StartLoadingUI(text) {
  $("#loading_info").html(text);
  $("#overlay").show();
}

function StopLoadingUI() {
  $("#overlay").hide();
}

function SetupGameUI() {
  console.log('Starting game UI');
  // Stop request available game timer.
  if (listing_game_timeout !== null) {
    window.clearTimeout(listing_game_timeout);
  }
  if (lobby_info_timeout !== null) {
    window.clearTimeout(lobby_info_timeout);
  }
  if (race_status_timeout !== null) {
    window.clearTimeout(race_status_timeout);
  }
  if (play_move_timeout !== null) {
    window.clearTimeout(play_move_timeout);
  }
  // Prepare UI.
  $("#title").html("Game");
  $("#user_info").hide();
  $("#list_games").hide();
  $("#create_game").hide();
  $("#game_lobby").hide();
  $("#game_play").show();
  $("#game_play_leave").unbind().click(function() {
    LeaveGamePlay();
  });
  game_canvas = $("#circuit_canvas");
  game_canvas.unbind();
  game_canvas.on('mousemove', CanvasMouseMoved);
  game_canvas.on('click', CanvasMouseClicked);
  game_canvas.on('touchend', CanvasTapEnd);
  game_canvas.on('touchmove', CanvasTapMove);
  game_canvas.on('taphold', CanvasTapHold);
  $(document).on('scrollstart', DocumentScroll);
  $("#circuit_info").draggable();
  // Request circuit data.
  RequestCircuitData();
}

function SetupGameLobbyUI() {
  console.log("Game lobby UI joined: " + game + ", as user: " + user + ", creator: " + is_creator);
  // Stop request available game timer.
  if (listing_game_timeout !== null) {
    window.clearTimeout(listing_game_timeout);
  }
  if (lobby_info_timeout !== null) {
    window.clearTimeout(lobby_info_timeout);
  }
  if (race_status_timeout !== null) {
    window.clearTimeout(race_status_timeout);
  }
  if (play_move_timeout !== null) {
    window.clearTimeout(play_move_timeout);
  }
  // Prepare UI.
  $("#title").html("Game lobby");
  $("#user_info").hide();
  $("#list_games").hide();
  $("#create_game").hide();
  $("#game_lobby").show();
  $("#game_play").hide();
  $("#game_lobby_leave").unbind().click(function() {
    LeaveGameLobby();
  });
  if (is_creator) {
    $(".game_lobby_admin_row").show();
    $("#game_lobby_start").unbind().click(function() {
      StartGame();
    });
  } else {
    $(".game_lobby_admin_row").hide();
  }
  $("#circuit_canvas").unbind();
  $(document).off("scroll");
  // Request lobby info.
  RequestLobbyInfo();
  RequestAvailableComputerAI();
}

function SetupListingUI() {
  console.log('Listing UI');
  game = null;
  // Stop request available game timer.
  if (lobby_info_timeout !== null) {
    window.clearTimeout(lobby_info_timeout);
  }
  if (listing_game_timeout !== null) {
    window.clearTimeout(listing_game_timeout);
  }
  if (race_status_timeout !== null) {
    window.clearTimeout(race_status_timeout);
  }
  if (play_move_timeout !== null) {
    window.clearTimeout(play_move_timeout);
  }
  // Prepare UI.
  $("#title").html("Welcome " + player_name);
  $("#user_info").hide();
  $("#list_games").show();
  $("#create_game").show();
  $("#game_lobby").hide();
  $("#game_play").hide();
  // Create game button.
  $("#create_game_button").unbind().click(function() {
    CreateNewGame();
  });
  $("#circuit_canvas").unbind();
  $(document).off("scroll");
  // Request the list of ongoing joinable games.
  RequestAvailableGames();
  RequestAvailableCircuitNames();
}

function SetupRegisterUI() {
  console.log('Register UI');
  player_name = null;
  // Stop request available game timer.
  if (lobby_info_timeout !== null) {
    window.clearTimeout(lobby_info_timeout);
  }
  if (listing_game_timeout !== null) {
    window.clearTimeout(listing_game_timeout);
  }
  if (race_status_timeout !== null) {
    window.clearTimeout(race_status_timeout);
  }
  if (play_move_timeout !== null) {
    window.clearTimeout(play_move_timeout);
  }
  // Prepare UI.
  $("#title").html("Welcome to CirKuit 2D");
  $("#user_info").show();
  $("#list_games").hide();
  $("#create_game").hide();
  $("#game_lobby").hide();
  $("#game_play").hide();
  // Create game button.
  $("#register_user_button").unbind().click(function() {
    RegisterUser();
  });
  $("#circuit_canvas").unbind();
  $(document).off("scroll");
}

///////////////////////
// Entry function.   //
///////////////////////

$(document).ready(function() {
  // Disable context menu everywhere.
  window.oncontextmenu = function(event) {
    event.preventDefault();
    event.stopPropagation();
    return false;
  };
  SetupRegisterUI();
});
