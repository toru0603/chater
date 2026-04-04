const joinBtn = document.getElementById("joinBtn");
const leaveBtn = document.getElementById("leaveBtn");
const statusEl = document.getElementById("status");
const nameInput = document.getElementById("name");
const roomCodeInput = document.getElementById("roomCode");
const localVideo = document.getElementById("localVideo");
const remoteVideo = document.getElementById("remoteVideo");

let socket = null;
let peerConnection = null;
let localStream = null;
let pendingCandidates = [];
let currentRole = null;

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

function ensurePeerConnection() {
  if (peerConnection) {
    return peerConnection;
  }

  peerConnection = new RTCPeerConnection(rtcConfig);
  localStream.getTracks().forEach((track) => peerConnection.addTrack(track, localStream));

  peerConnection.onicecandidate = (event) => {
    if (event.candidate) {
      send({ type: "candidate", data: event.candidate });
    }
  };

  peerConnection.ontrack = (event) => {
    remoteVideo.srcObject = event.streams[0];
  };

  peerConnection.onconnectionstatechange = () => {
    setStatus(`接続状態: ${peerConnection.connectionState}`);
  };

  return peerConnection;
}

async function flushPendingCandidates() {
  if (!peerConnection || !peerConnection.remoteDescription) {
    return;
  }
  const items = pendingCandidates;
  pendingCandidates = [];
  for (const candidate of items) {
    await peerConnection.addIceCandidate(candidate);
  }
}

async function startOffer() {
  const pc = ensurePeerConnection();
  const offer = await pc.createOffer();
  await pc.setLocalDescription(offer);
  send({ type: "offer", data: pc.localDescription });
}

async function handleSignal(message) {
  const pc = ensurePeerConnection();

  if (message.signal_type === "offer") {
    await pc.setRemoteDescription(new RTCSessionDescription(message.data));
    await flushPendingCandidates();
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    send({ type: "answer", data: pc.localDescription });
    return;
  }

  if (message.signal_type === "answer") {
    await pc.setRemoteDescription(new RTCSessionDescription(message.data));
    await flushPendingCandidates();
    return;
  }

  if (message.signal_type === "candidate") {
    const candidate = new RTCIceCandidate(message.data);
    if (pc.remoteDescription) {
      await pc.addIceCandidate(candidate);
    } else {
      pendingCandidates.push(candidate);
    }
  }
}

async function startCall() {
  const roomCode = roomCodeInput.value.trim();
  const name = nameInput.value.trim() || "Guest";

  if (!roomCode) {
    setStatus("待ち受け番号を入力してください");
    return;
  }

  try {
    localStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
    localVideo.srcObject = localStream;
  } catch (error) {
    setStatus(`カメラ/マイクを取得できません: ${error.message}`);
    return;
  }

  socket = new WebSocket(`ws://${location.host}/ws/${encodeURIComponent(roomCode)}`);
  socket.onopen = () => {
    send({ type: "join", name });
    setStatus("サーバに接続しました");
    joinBtn.disabled = true;
    leaveBtn.disabled = false;
  };

  socket.onmessage = async (event) => {
    const message = JSON.parse(event.data);

    if (message.type === "waiting") {
      setStatus(message.message);
      return;
    }

    if (message.type === "joined") {
      setStatus(`参加しました: ${message.room_code}`);
      return;
    }

    if (message.type === "matched") {
      currentRole = message.role;
      setStatus(`マッチ成功: 相手は ${message.peer_name}`);
      ensurePeerConnection();
      if (currentRole === "host") {
        await startOffer();
      }
      return;
    }

    if (message.type === "signal") {
      await handleSignal(message);
      return;
    }

    if (message.type === "peer-left") {
      setStatus("相手が退出しました");
      return;
    }

    if (message.type === "error") {
      setStatus(message.message);
    }
  };

  socket.onclose = () => {
    joinBtn.disabled = false;
    leaveBtn.disabled = true;
    setStatus("切断しました");
  };
}

function leaveCall() {
  send({ type: "leave" });
  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
  }
  if (socket) {
    socket.close();
    socket = null;
  }
  if (localStream) {
    localStream.getTracks().forEach((track) => track.stop());
    localStream = null;
  }
  remoteVideo.srcObject = null;
  localVideo.srcObject = null;
  joinBtn.disabled = false;
  leaveBtn.disabled = true;
  pendingCandidates = [];
  currentRole = null;
  setStatus("待機中");
}

joinBtn.addEventListener("click", startCall);
leaveBtn.addEventListener("click", leaveCall);

window.addEventListener("beforeunload", () => {
  if (socket) {
    socket.close();
  }
});
