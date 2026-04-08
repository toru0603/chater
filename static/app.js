const joinBtn = document.getElementById("joinBtn");
const leaveBtn = document.getElementById("leaveBtn");
const statusEl = document.getElementById("status");
const nameInput = document.getElementById("name");
const roomCodeInput = document.getElementById("roomCode");
const localVideo = document.getElementById("localVideo");
const videosContainer = document.getElementById("videos");

// chat elements
const messageInput = document.getElementById("messageInput");
const sendMsgBtn = document.getElementById("sendMsgBtn");
const danmakuContainer = document.getElementById("danmaku");

let socket = null;
let localStream = null;
const peers = {}; // peerId -> RTCPeerConnection
const remoteVideos = {}; // peerId -> HTMLVideoElement
const pendingCandidates = {}; // peerId -> []
const participantColors = {}; // peerId -> color
let ownParticipantId = null;
let ownName = null;

const rtcConfig = {
  iceServers: [{ urls: "stun:stun.l.google.com:19302" }],
};

function setStatus(message) {
  statusEl.textContent = message;
}

function send(payload) {
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload));
  }
}

function createRemoteVideoElement(peerId, name) {
  if (remoteVideos[peerId]) return remoteVideos[peerId];
  const tile = document.createElement('div');
  tile.className = 'video-tile';
  tile.dataset.peerId = peerId;

  const title = document.createElement('h3');
  title.textContent = name || peerId;
  if (participantColors[peerId]) title.style.color = participantColors[peerId];
  tile.appendChild(title);

  const vid = document.createElement('video');
  vid.autoplay = true;
  vid.playsInline = true;
  vid.muted = false;
  tile.appendChild(vid);

  videosContainer.appendChild(tile);
  remoteVideos[peerId] = vid;
  return vid;
}

function removeRemoteVideoElement(peerId) {
  const vid = remoteVideos[peerId];
  if (vid) {
    const tile = vid.parentElement;
    if (tile && tile.parentElement) tile.parentElement.removeChild(tile);
    try { vid.srcObject = null; } catch (e) {}
    delete remoteVideos[peerId];
  }
}

function ensurePeerConnection(peerId) {
  if (peers[peerId]) return peers[peerId];
  const pc = new RTCPeerConnection(rtcConfig);

  pc.onicecandidate = (event) => {
    if (event.candidate) {
      send({ type: 'candidate', target: peerId, data: event.candidate });
    }
  };

  pc.ontrack = (event) => {
    const vid = createRemoteVideoElement(peerId, 'Peer');
    vid.srcObject = event.streams[0];
  };

  pc.onconnectionstatechange = () => {
    setStatus(`接続状態: ${pc.connectionState}`);
    if (pc.connectionState === 'failed' || pc.connectionState === 'closed' || pc.connectionState === 'disconnected') {
      removeRemoteVideoElement(peerId);
      try { pc.close(); } catch (e) {}
      delete peers[peerId];
    }
  };

  if (localStream) {
    localStream.getTracks().forEach(track => pc.addTrack(track, localStream));
  }

  peers[peerId] = pc;
  pendingCandidates[peerId] = [];
  return pc;
}

async function flushPendingCandidates(peerId) {
  const pc = peers[peerId];
  if (!pc || !pc.remoteDescription) return;
  const items = pendingCandidates[peerId] || [];
  pendingCandidates[peerId] = [];
  for (const c of items) {
    try { await pc.addIceCandidate(c); } catch (e) { console.warn('addIce failed', e); }
  }
}

async function handleSignal(message) {
  const from = message.from;
  const type = message.signal_type;
  const data = message.data;

  if (!from) return;

  if (type === 'offer') {
    const pc = ensurePeerConnection(from);
    await pc.setRemoteDescription(new RTCSessionDescription(data));
    await flushPendingCandidates(from);
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    send({ type: 'answer', target: from, data: pc.localDescription });
    return;
  }

  if (type === 'answer') {
    const pc = ensurePeerConnection(from);
    await pc.setRemoteDescription(new RTCSessionDescription(data));
    await flushPendingCandidates(from);
    return;
  }

  if (type === 'candidate') {
    const candidate = new RTCIceCandidate(data);
    const pc = peers[from];
    if (pc && pc.remoteDescription) {
      try { await pc.addIceCandidate(candidate); } catch (e) { console.warn('addIce', e); }
    } else {
      (pendingCandidates[from] = pendingCandidates[from] || []).push(candidate);
    }
  }
}

// Danmaku functions
function addDanmaku(fromId, name, text, color) {
  if (!danmakuContainer) return;
  const msg = document.createElement('div');
  msg.className = 'danmaku-message';

  const nameSpan = document.createElement('span');
  nameSpan.textContent = name ? `${name}: ` : '';
  nameSpan.style.color = color || participantColors[fromId] || '#fff';
  nameSpan.style.fontWeight = '700';
  nameSpan.style.marginRight = '8px';
  msg.appendChild(nameSpan);

  const textSpan = document.createElement('span');
  textSpan.textContent = text || '';
  msg.appendChild(textSpan);

  const containerHeight = danmakuContainer.clientHeight || (videosContainer.clientHeight || 300);
  const laneHeight = 34;
  const maxTop = Math.max(0, containerHeight - laneHeight);
  const top = Math.floor(Math.random() * (maxTop + 1));
  msg.style.top = `${top}px`;
  const duration = (Math.random() * 6) + 8; // seconds
  msg.style.setProperty('--duration', `${duration}s`);
  danmakuContainer.appendChild(msg);
  msg.addEventListener('animationend', () => {
    try { danmakuContainer.removeChild(msg); } catch (e) {}
  });
}

// message sending
function sendMessage() {
  const text = messageInput ? messageInput.value.trim() : '';
  if (!text) return;
  if (!socket || socket.readyState !== WebSocket.OPEN) { setStatus('未接続'); return; }
  send({ type: 'chat', text });
  if (messageInput) messageInput.value = '';
}

if (sendMsgBtn) sendMsgBtn.addEventListener('click', sendMessage);
if (messageInput) messageInput.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') sendMessage();
});

async function startCall() {
  const roomCode = roomCodeInput.value.trim();
  const name = nameInput.value.trim() || 'Guest';

  if (!roomCode) { setStatus('待ち受け番号を入力してください'); return; }

  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    localVideo.srcObject = localStream;
  } catch (err) {
    setStatus(`カメラ/マイクを取得できません: ${err.message}`);
    return;
  }

  socket = new WebSocket(`ws://${location.host}/ws/${encodeURIComponent(roomCode)}`);
  socket.onopen = () => {
    send({ type: 'join', name });
    setStatus('サーバに接続しました');
    joinBtn.disabled = true; leaveBtn.disabled = false;
  };

  socket.onmessage = async (ev) => {
    const message = JSON.parse(ev.data);

    if (message.type === 'waiting') { setStatus(message.message); return; }
    if (message.type === 'joined') {
      // store own id and color and update local title
      ownParticipantId = message.participant_id;
      ownName = message.name || ownName;
      if (message.color) participantColors[ownParticipantId] = message.color;
      const localTile = localVideo ? localVideo.parentElement : null;
      if (localTile) {
        const title = localTile.querySelector('h3');
        if (title) {
          title.textContent = ownName || title.textContent;
          title.style.color = participantColors[ownParticipantId] || title.style.color;
        }
        // Keep the local tile's data-peer-id stable to avoid selector issues on rejoin
      }
      setStatus(`参加しました: ${message.room_code}`);
      return; }

    if (message.type === 'participants') {
      setStatus('既存参加者が見つかりました');
      const parts = message.participants || [];
      // register colors first so titles get colored
      for (const p of parts) {
        if (p.color) participantColors[p.id] = p.color;
      }
      // create peer connections and initiate offers to existing participants
      for (const p of parts) {
        createRemoteVideoElement(p.id, p.name);
        const tile = document.querySelector(`[data-peer-id="${p.id}"]`);
        if (tile) {
          const title = tile.querySelector('h3');
          if (title && participantColors[p.id]) title.style.color = participantColors[p.id];
        }
        const pc = ensurePeerConnection(p.id);
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        send({ type: 'offer', target: p.id, data: pc.localDescription });
      }
      return;
    }

    if (message.type === 'participant-joined') {
      setStatus(`参加者が増えました: ${message.name}`);
      if (message.color) participantColors[message.id] = message.color;
      createRemoteVideoElement(message.id, message.name);
      const tile = document.querySelector(`[data-peer-id="${message.id}"]`);
      if (tile) {
        const title = tile.querySelector('h3');
        if (title && participantColors[message.id]) title.style.color = participantColors[message.id];
      }
      return;
    }

    if (message.type === 'signal') {
      await handleSignal(message);
      return;
    }

    if (message.type === 'participant-left') {
      setStatus(`${message.name} が退出しました`);
      removeRemoteVideoElement(message.id);
      // close pc if exists
      if (peers[message.id]) { try { peers[message.id].close(); } catch(e){} delete peers[message.id]; }
      return;
    }

    if (message.type === 'chat') {
      // remember color and show danmaku with colored name
      if (message.color) participantColors[message.from] = message.color;
      addDanmaku(message.from, message.from_name || '匿名', message.text || '', message.color || participantColors[message.from]);
      return;
    }

    if (message.type === 'error') { setStatus(message.message); }
  };

  socket.onclose = () => {
    joinBtn.disabled = false; leaveBtn.disabled = true; setStatus('切断しました');
  };
}

function leaveCall() {
  send({ type: 'leave' });
  try { Object.values(peers).forEach(pc => pc.close()); } catch (e) {}
  Object.keys(peers).forEach(k => delete peers[k]);
  Object.keys(remoteVideos).forEach(k => removeRemoteVideoElement(k));
  if (socket) { socket.close(); socket = null; }
  if (localStream) { localStream.getTracks().forEach(t => t.stop()); localStream = null; }
  localVideo.srcObject = null;
  joinBtn.disabled = false; leaveBtn.disabled = true; setStatus('待機中');
}

joinBtn.addEventListener('click', startCall);
leaveBtn.addEventListener('click', leaveCall);

window.addEventListener('beforeunload', () => { if (socket) socket.close(); });
