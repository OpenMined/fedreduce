let serverPort = 8080; // Default port
let metadataDatasite = ""; // Placeholder for the datasite

// Function to save the port to localStorage
function savePort() {
  try {
    const portInput = document.getElementById("server-port").value;
    localStorage.setItem("serverPort", portInput);
    serverPort = portInput;
    checkServerStatus();
    fetchMetadata();
  } catch (error) {
    console.error("Error accessing localStorage:", error);
  }
}

// Retrieve saved port from localStorage on page load
document.addEventListener("DOMContentLoaded", () => {
  try {
    const savedPort = localStorage.getItem("serverPort");
    if (savedPort) {
      serverPort = savedPort;
      document.getElementById("server-port").value = savedPort;
    }
  } catch (error) {
    console.error("Error accessing localStorage:", error);
  }

  fetchMetadata();
  fetchProjects();
  checkServerStatus();
});

document.getElementById("server-port").addEventListener("input", (event) => {
  serverPort = event.target.value;
  checkServerStatus();
  fetchMetadata(); // Fetch metadata when port changes
});

async function fetchMetadata() {
  try {
    const response = await fetch(`http://localhost:${serverPort}/metadata`);
    if (response.ok) {
      const data = await response.json();
      metadataDatasite = data.datasite || "";
      console.log("Metadata datasite:", metadataDatasite); // Debugging
    }
  } catch (error) {
    console.error("Error fetching metadata:", error);
  }
}

async function fetchProjects() {
  try {
    const container = document.getElementById("available-projects");
    container.innerHTML = '<div class="loading">Loading projects...</div>';

    const response = await fetch("./activity.json");
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    console.log("Loaded data:", data); // For debugging

    // Check joined projects state
    const joinedProjects = await fetchJoinedProjects();

    renderProjects(data, joinedProjects);
  } catch (error) {
    console.error("Error loading projects:", error);
    document.getElementById("available-projects").innerHTML =
      '<div class="loading">Error loading projects. Please try again later.</div>';
  }
}

async function fetchJoinedProjects() {
  const url = `http://localhost:${serverPort}/apps/command/fedreduce`;
  const payload = { command: "list_projects" };

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      const projects = await response.json();
      return projects
        .filter(
          (project) => project.state === "join" || project.state === "running"
        )
        .map((project) => ({
          state: project.state,
          sourceUrl: project.sourceUrl[0], // Extract the sourceUrl as a string
        }));
    } else {
      console.error("Failed to fetch joined projects.");
      return [];
    }
  } catch (error) {
    console.error("Error fetching joined projects:", error);
    return [];
  }
}

function createProjectCard(project, status, joinedProjects) {
  const isJoined = joinedProjects.some(
    (p) => p.sourceUrl === project.sourceUrl
  );

  // Include metadataDatasite if the project is joined
  const datasites = isJoined
    ? project.datasites.includes(metadataDatasite)
      ? project.datasites
      : [...project.datasites, metadataDatasite]
    : project.datasites;

  const isAuthor = metadataDatasite === project.author;

  return `
    <div class="project-card">
        <div class="project-title">${project.name}</div>
        <div class="project-info">
            <div class="info-item">
                <span class="info-label">Date:</span>
                <span>${formatDate(project.file_timestamp * 1000)}</span>
            </div>
            <div class="info-item">
                <span class="info-label">UID:</span>
                <span>${project.uid}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Description:</span>
                <span>${project.description}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Language:</span>
                <span>${project.language}</span>
            </div>
            <div class="info-item">
                <span class="info-label">Author:</span>
                <span>${project.author}</span>
            </div>
        </div>

        <div class="project-links">
            <a href="${project.sourceUrl}">Source</a>
        </div>

        <div class="info-item">
            <span class="info-label">Shared Inputs:</span>
            <span>${project.sharedInputs}</span>
        </div>

        <div class="info-item">
            <span class="info-label">Datasites:</span>
            <ul class="datasites-list">
                ${datasites.map((site) => `<li>${site}</li>`).join("")}
            </ul>
        </div>

        <div class="info-item">
            <span class="info-label"><a href="${
              project.sourceUrl
            }">Code Files</a>:</span>
            <ul class="code-list">
                ${Object.entries(project.code || {})
                  .map(([file, url]) => `<li><a href="${url}">${file}</a></li>`)
                  .join("")}
            </ul>
        </div>

        ${getActionButton(status, project, isJoined, isAuthor)}
    </div>
  `;
}

function renderProjects(data, joinedProjects) {
  renderProjectSection(
    "available-projects",
    data.invite,
    "invite",
    joinedProjects
  );
  renderProjectSection(
    "running-projects",
    data.running,
    "running",
    joinedProjects
  );
  renderProjectSection(
    "completed-projects",
    data.completed,
    "completed",
    joinedProjects
  );
}

function renderProjectSection(containerId, projects, status, joinedProjects) {
  const container = document.getElementById(containerId);
  container.innerHTML = projects
    .map((project) => createProjectCard(project, status, joinedProjects))
    .join("");
}

function getActionButton(status, project, isJoined, isAuthor) {
  console.log(status, project, isJoined, isAuthor); // Debugging

  let actionButtons = "";

  // If the project is in "invite" status, show Join/Leave button based on isJoined status
  if (status === "invite") {
    actionButtons += isJoined
      ? `<button class="leave-button" onclick="leaveProject('${project.sourceUrl}')">Leave Project</button>`
      : `<button class="join-button" onclick="joinProject('${project.sourceUrl}')">Join Project</button>`;
  }

  // If the user is the author, show the "Start" button for invite status
  if (status === "invite" && isAuthor) {
    actionButtons += `<button class="start-button" onclick="startProject('${project.sourceUrl}')">Start</button>`;
  }

  // Show the "View Results" link if the project is completed
  if (status === "completed") {
    actionButtons += `<a href="${project.resultUrl}" class="result-link">View Results</a>`;
  }

  return actionButtons;
}

async function startProject(sourceUrl) {
  const url = `http://localhost:${serverPort}/apps/command/fedreduce`;
  const payload = {
    command: "start",
    source: sourceUrl,
  };

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      alert("Project started successfully!");
      fetchProjects(); // Refresh projects to move it to running
    } else {
      alert("Failed to start project.");
    }
  } catch (error) {
    console.error("Error starting project:", error);
    alert("Error connecting to the server.");
  }
}

async function joinProject(sourceUrl) {
  const url = `http://localhost:${serverPort}/apps/command/fedreduce`;
  const payload = {
    command: "join",
    state: "join",
    source: sourceUrl,
  };

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      alert("Successfully joined project!");
      fetchProjects(); // Refresh projects to update the button
    } else {
      alert("Failed to join project.");
    }
  } catch (error) {
    console.error("Error joining project:", error);
    alert("Error connecting to the server.");
  }
}

async function leaveProject(sourceUrl) {
  const url = `http://localhost:${serverPort}/apps/command/fedreduce`;
  const payload = {
    command: "join",
    state: "leave",
    source: sourceUrl,
  };

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (response.ok) {
      alert("Successfully left project!");
      fetchProjects(); // Refresh projects to update the button
    } else {
      alert("Failed to leave project.");
    }
  } catch (error) {
    console.error("Error leaving project:", error);
    alert("Error connecting to the server.");
  }
}

function formatDate(timestamp) {
  return new Date(timestamp).toLocaleString();
}

async function checkServerStatus() {
  const serverStatus = document.getElementById("server-status");
  try {
    const response = await fetch(`http://localhost:${serverPort}/apps/`);
    if (response.ok) {
      serverStatus.textContent = "✔️";
      serverStatus.classList.remove("error");
      serverStatus.classList.add("success");
    } else {
      throw new Error("Non-200 response");
    }
  } catch {
    serverStatus.textContent = "❌";
    serverStatus.classList.remove("success");
    serverStatus.classList.add("error");
  }
}

document.getElementById("server-port").addEventListener("input", (event) => {
  serverPort = event.target.value;
  checkServerStatus();
  fetchMetadata(); // Refresh metadata after port change
});

document.addEventListener("DOMContentLoaded", () => {
  fetchMetadata();
  fetchProjects();
  checkServerStatus();
});
