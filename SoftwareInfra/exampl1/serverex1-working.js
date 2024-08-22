const EventEmitter = require('node:events');
const myEmitter = new EventEmitter();
const http = require('http');
const express = require('express');
const udp = require('dgram');
const { Buffer } = require('node:buffer');

const hostname = '10.208.57.90'; // eth0
let app = express();
var port = 8080;

const HEARTBEAT_INTERVAL = 1000; // 1 second
const MAX_WAIT_COUNT = 1000;    // number of times to wait for target readiness before logging

let heartbeatWaitCount = 0;
let heartbeatTimer = null;

class httpclass {
  setRequest(request) {
    this.request = request;
  }
  setResponse(response) {
    this.response = response;
  }
  getRequest() {
    return this.request;
  }
  getResponse() {
    return this.response;
  }
}

class udpclass {
  setPort(port) {
    this.port = port;
  }
  setAddress(address) {
    this.address = address;
  }
  setMessage(message, length) {
    this.message = message;
    this.length = length;
  }
  getMessage() {
    return this.message;
  }
  getPort() {
    return this.port;
  }
  getAddress() {
    return this.address;
  }
}

myEmitter.on('addstack', function(data) {
  console.log('Data sent from server Data:%s port:%d address:%s\n', data.message, data.port, data.address);
  server.send(data.message, data.port, data.address, function(error) {
    if (error)
      console.log('Data not sent....!!!!!\n');
    else
      console.log('Data sent !!!!!\n');
  });
});

let udpobj = new udpclass();
let httpobj = new httpclass();

const httpserver = http.createServer(app);
httpserver.listen(port, hostname, () => {
  console.log(`Server running at http://${hostname}:${port}/`);
});

// creating a udp server
let server = udp.createSocket('udp4');

// emits when any error occurs
server.on('error', function(error) {
  console.log('Error: ' + error);
  server.close();
});

function receiveHttpReq(request, response) {
  if (request.query.reqcmd && request.query.reqcmd.trim() !== 'SYNC') {
    let port = udpobj.getPort();
    let address = udpobj.getAddress();
    if (port > 0 && port < 65536 && address) {
      server.send(request.query.reqcmd.trim(), port, address, function(error) {
        if (error) {
          console.log('Data not sent....!!!!!\n');
        } else {
          console.log('Data sent !!!!!\n');
          // Clear previous message
          udpobj.setMessage('', 0);
        }
      });
    } else {
      console.error('Port should be > 0 and < 65536. Received ' + port);
      response.status(400).send('Invalid port or address');
    }
  } else {
    console.error('No command provided or SYNC message ignored');
    response.status(400).send('No command provided or SYNC message ignored');
  }
}

function receiveUDPReq(msg) {
  let response = httpobj.getResponse();
  if (response) {
    udpobj.setMessage(udpobj.getMessage() + msg.toString() + '\n', msg.length);
  } else {
    console.error('HTTP response object is not defined');
  }
}

const cmd = Buffer.from('SYNC');

server.on('message', async function(msg, info) {
  try {
    console.log('Data received from client: ' + msg.toString().trim());
    console.log('Received %d bytes from %s:%d\n', msg.length, info.address, info.port);
    if (msg.toString().trim() === 'SYNC') {
      udpobj.setPort(info.port);
      udpobj.setAddress(info.address);
      server.send('SYNC', info.port, info.address, function(error) {
        if (error) {
          console.log('Data not sent....!!!!!\n');
        } else {
          console.log('Data sent !!!!!\n');
        }
      });
    } else if (msg.toString().trim() === 'Heartbeat') {
      console.log(`Heartbeat received from ${info.address}:${info.port} at ${new Date().toISOString()}`);
      heartbeatWaitCount = 0; // Reset wait count
    } else {
      receiveUDPReq(msg);
    }
  } catch (error) {
    console.error('Error processing UDP message:', error.message);
  }
});

app.get('/get_data', async function(req, res) {
  try {
    console.log(req.query.reqcmd.trim());
    httpobj.setRequest(req);
    httpobj.setResponse(res);
    await receiveHttpReq(req, res);
    // Wait for some time to accumulate the UDP responses before sending HTTP response
    setTimeout(() => {
      res.status(200).send(udpobj.getMessage());
    }, 1000); // 1 second delay to collect all UDP responses
  } catch (error) {
    console.error('Error processing HTTP message:', error.message);
    res.status(500).send('Internal Server Error');
  }
});

// emits when socket is ready and listening for datagram msgs
server.on('listening', function() {
  let address = server.address();
  let port = address.port;
  let family = address.family;
  let ipaddr = address.address;
  console.log('Server is listening at port ' + port);
  console.log('Server ip: ' + ipaddr);
  console.log('Server is IP4/IP6: ' + family);

  startHeartbeatCheck(); // Start the heartbeat check when the server starts
});

// emits after the socket is closed using socket.close();
server.on('close', function() {
  console.log('Socket is closed!');
  clearInterval(heartbeatTimer); // Stop the heartbeat timer when the socket is closed
});

function startHeartbeatCheck() {
  heartbeatTimer = setInterval(() => {
    if (heartbeatWaitCount >= MAX_WAIT_COUNT) {
      console.log('Target is not ready. Exceeded maximum wait count for heartbeat.');
    } else {
      console.log('Waiting for heartbeat...');
      heartbeatWaitCount++;
    }
  }, HEARTBEAT_INTERVAL);
}

server.bind(4444, '190.20.20.2'); // usb0
