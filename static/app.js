const joinBtn = document.getElementById("joinBtn");
const leaveBtn = document.getElementById("leaveBtn");
const statusEl = document.getElementById("status");
const nameInput = document.getElementById("name");
const roomCodeInput = document.getElementById("roomCode");
const localVideo = document.getElementById("localVideo");
const videosContainer = document.getElementById("videos");

let socket = null;
let localStream = null;
const peers = {}; // peerId -> RTCPeerConnection
const remoteVideos = {}; // peerId -> HTMLVideoElement
const pendingCandidates = {}; // peerId -> []

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
    if (message.type === 'joined') { setStatus(`参加しました: ${message.room_code}`); return; }

    if (message.type === 'participants') {
      setStatus('既存参加者が見つかりました');
      const parts = message.participants || [];
      // create peer connections and initiate offers to existing participants
      for (const p of parts) {
        createRemoteVideoElement(p.id, p.name);
        const pc = ensurePeerConnection(p.id);
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        send({ type: 'offer', target: p.id, data: pc.localDescription });
      }
      return;
    }

    if (message.type === 'participant-joined') {
      setStatus(`参加者が増えました: ${message.name}`);
      // wait for incoming offer from the new participant
      createRemoteVideoElement(message.id, message.name);
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
