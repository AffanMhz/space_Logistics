document.addEventListener('DOMContentLoaded', () => {
  console.log('Space Station Cargo Management System initialized');
  
  // Initialize date display
  const currentDateDisplay = document.getElementById('currentDateDisplay');
  if (currentDateDisplay) {
    currentDateDisplay.textContent = new Date().toISOString().split('T')[0];
  }
  
  // Tab navigation
  const tabs = {
    'homeBtn': 'home-tab',
    'containersBtn': 'container-tab',
    'itemsBtn': 'items-tab',
    'searchBtn': 'search-tab',
    'wasteBtn': 'waste-tab',
    'simulationBtn': 'simulation-tab',
    'logsBtn': 'logs-tab',
    'threeDBtn': 'threeD-tab'
  };
  
  Object.keys(tabs).forEach(btnId => {
    const btn = document.getElementById(btnId);
    if (btn) {
      btn.addEventListener('click', () => {
        // Hide all tabs
        Object.values(tabs).forEach(tabId => {
          const tabElement = document.getElementById(tabId);
          if (tabElement) {
            tabElement.style.display = 'none';
          }
        });
        
        // Show selected tab
        const tabToShow = document.getElementById(tabs[btnId]);
        if (tabToShow) {
          tabToShow.style.display = 'block';
        }
        
        // Update active button
        Object.keys(tabs).forEach(id => {
          const button = document.getElementById(id);
          if (button) {
            button.classList.remove('active');
          }
        });
        btn.classList.add('active');
        
        // Special handling for 3D view tab - load containers automatically
        if (btnId === 'threeDBtn' && threeDViewerInstance) {
          // Load containers for the 3D view
          fetch('/api/containers')
            .then(response => response.json())
            .then(containers => {
              if (containers.length > 0) {
                // Create all containers in the 3D viewer
                threeDViewerInstance.createContainers(containers);
                console.log(`Loaded ${containers.length} containers into 3D view`);
              }
            })
            .catch(error => console.error('Error loading containers for 3D view:', error));
        }
      });
    }
  });
  
  // Initialize container viewers
  const threeDViewer = document.getElementById('threeDViewer');
  const itemLocationViewer = document.getElementById('itemLocationViewer');
  
  let threeDViewerInstance = null;
  let itemLocationViewerInstance = null;
  
  if (threeDViewer) {
    threeDViewerInstance = new ISSContainerViewer(threeDViewer);
  }
  
  if (itemLocationViewer) {
    itemLocationViewerInstance = new ISSContainerViewer(itemLocationViewer);
  }
  
  // Data loading functions
  async function loadContainers() {
    try {
      const response = await fetch('/api/containers');
      if (response.ok) {
        const containers = await response.json();
        displayContainers(containers);
        return containers;
      } else {
        console.error('Failed to load containers:', response.statusText);
        return [];
      }
    } catch (error) {
      console.error('Error loading containers:', error);
      return [];
    }
  }
  
  async function loadItems() {
    try {
      const response = await fetch('/api/items');
      if (response.ok) {
        const items = await response.json();
        displayItems(items);
        return items;
      } else {
        console.error('Failed to load items:', response.statusText);
        return [];
      }
    } catch (error) {
      console.error('Error loading items:', error);
      return [];
    }
  }
  
  async function loadLogs() {
    try {
      const response = await fetch('/api/logs');
      if (response.ok) {
        const logs = await response.json();
        displayLogs(logs);
        
        // Update current date from the most recent log if available
        if (logs.length > 0 && logs[0].currentDate) {
          const currentDate = new Date(logs[0].currentDate);
          if (currentDateDisplay) {
            currentDateDisplay.textContent = currentDate.toISOString().split('T')[0];
          }
          
          const currentDateValue = document.getElementById('currentDateValue');
          if (currentDateValue) {
            currentDateValue.textContent = currentDate.toLocaleDateString('en-US', {
              weekday: 'long',
              year: 'numeric', 
              month: 'long', 
              day: 'numeric'
            });
          }
        }
        
        return logs;
      } else {
        console.error('Failed to load logs:', response.statusText);
        return [];
      }
    } catch (error) {
      console.error('Error loading logs:', error);
      return [];
    }
  }
  
  // Display functions
  function displayContainers(containers) {
    const containerGrid = document.getElementById('containerGrid');
    if (!containerGrid) return;
    
    containerGrid.innerHTML = '';
    
    if (containers.length === 0) {
      containerGrid.innerHTML = '<p class="text-center">No containers available. Import containers first.</p>';
      return;
    }
    
    containers.forEach(container => {
      const containerDiv = document.createElement('div');
      containerDiv.className = 'container-item';
      containerDiv.style.backgroundColor = getZoneColor(container.zone);
      
      const totalVolume = container.width * container.depth * container.height;
      const usagePercent = container.occupiedSpace > 0 
        ? Math.round((container.occupiedSpace / totalVolume) * 100) 
        : 0;
      
      containerDiv.innerHTML = `
        <h4>${container.containerId}</h4>
        <p>Zone: ${container.zone}</p>
        <p>${container.width}cm × ${container.depth}cm × ${container.height}cm</p>
        <div class="progress mb-2">
          <div class="progress-bar ${usagePercent > 80 ? 'bg-danger' : 'bg-success'}" 
               role="progressbar" 
               style="width: ${usagePercent}%" 
               aria-valuenow="${usagePercent}" 
               aria-valuemin="0" 
               aria-valuemax="100">
            ${usagePercent}%
          </div>
        </div>
        <p>${container.items.length} items</p>
      `;
      
      containerDiv.addEventListener('click', () => {
        // Show in 3D viewer
        if (threeDViewerInstance) {
          threeDViewerInstance.createContainers([container]);
        }
      });
      
      containerGrid.appendChild(containerDiv);
    });
  }
  
  function displayItems(items) {
    const itemsTableBody = document.getElementById('itemsTableBody');
    if (!itemsTableBody) return;
    
    itemsTableBody.innerHTML = '';
    
    if (items.length === 0) {
      itemsTableBody.innerHTML = '<tr><td colspan="8" class="text-center">No items available. Import items first.</td></tr>';
      return;
    }
    
    items.forEach(item => {
      const priorityClass = item.priority > 80 ? 'priority-high' : 
                           item.priority > 50 ? 'priority-medium' : 'priority-low';
      
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${item.itemId}</td>
        <td>${item.name}</td>
        <td class="${priorityClass}">${item.priority}</td>
        <td>${item.width}cm × ${item.depth}cm × ${item.height}cm</td>
        <td>${item.mass} kg</td>
        <td>${item.expiryDate}</td>
        <td>${item.preferredZone}</td>
        <td>
          <button class="btn btn-sm btn-primary search-item-btn" data-item-id="${item.itemId}">
            Find
          </button>
        </td>
      `;
      
      // Add event listener to search button
      row.querySelector('.search-item-btn').addEventListener('click', () => {
        // Switch to search tab and search for this item
        document.getElementById('searchBtn').click();
        document.getElementById('searchInput').value = item.itemId;
        document.getElementById('searchItemBtn').click();
      });
      
      itemsTableBody.appendChild(row);
    });
  }
  
  function displayLogs(logs) {
    const systemLogs = document.getElementById('systemLogs');
    if (!systemLogs) return;
    
    systemLogs.innerHTML = '';
    
    if (logs.length === 0) {
      systemLogs.innerHTML = '<p class="text-center">No system logs available.</p>';
      return;
    }
    
    logs.forEach(log => {
      const logEntry = document.createElement('div');
      logEntry.className = 'log-entry';
      
      const timestamp = new Date(log.timestamp);
      const formattedTime = timestamp.toLocaleString();
      
      logEntry.innerHTML = `
        <span class="timestamp">[${formattedTime}]</span>
        <span class="user">${log.user}:</span>
        <span class="action">${log.action}</span>
        ${log.details ? `<div class="small text-muted mt-1">${JSON.stringify(log.details)}</div>` : ''}
      `;
      
      systemLogs.appendChild(logEntry);
    });
  }
  
  // Helper functions
  function getZoneColor(zone) {
    const colors = {
      'Crew_Quarters': 'rgba(165, 216, 255, 0.3)',
      'Sanitation_Bay': 'rgba(255, 216, 168, 0.3)',
      'Command_Center': 'rgba(216, 245, 162, 0.3)',
      'Engineering_Bay': 'rgba(248, 249, 250, 0.3)',
      'Medical_Bay': 'rgba(255, 193, 193, 0.3)',
      'Storage_Bay': 'rgba(216, 216, 255, 0.3)',
      'Life_Support': 'rgba(200, 255, 200, 0.3)',
      'Airlock': 'rgba(240, 200, 255, 0.3)',
      'Maintenance_Bay': 'rgba(255, 255, 200, 0.3)',
      'External_Storage': 'rgba(200, 200, 200, 0.3)'
    };
    
    return colors[zone] || 'rgba(200, 200, 200, 0.3)';
  }
  
  // Event handlers for file imports
  const setupFileImport = (fileInputId, importBtnId, uploadEndpoint, onSuccess) => {
    const fileInput = document.getElementById(fileInputId);
    const importBtn = document.getElementById(importBtnId);
    
    if (fileInput && importBtn) {
      importBtn.addEventListener('click', () => {
        fileInput.click();
      });
      
      fileInput.addEventListener('change', async (e) => {
        if (e.target.files.length === 0) return;
        
        const file = e.target.files[0];
        const formData = new FormData();
        formData.append('file', file);
        
        try {
          const response = await fetch(uploadEndpoint, {
            method: 'POST',
            body: formData
          });
          
          if (response.ok) {
            const result = await response.json();
            alert(`Import successful: ${result.importedCount || 'unknown'} items imported.`);
            
            if (typeof onSuccess === 'function') {
              onSuccess();
            }
          } else {
            alert(`Import failed: ${response.statusText}`);
          }
        } catch (error) {
          console.error('Import error:', error);
          alert(`Import error: ${error.message}`);
        }
      });
    }
  };
  
  // Setup all import buttons
  setupFileImport('containerFileInput', 'importContainersBtn', '/api/containers/import', loadContainers);
  setupFileImport('itemFileInput', 'importItemsBtn', '/api/items/import', loadItems);
  
  // Calculate placement button
  const calculatePlacementBtn = document.getElementById('calculatePlacementBtn');
  if (calculatePlacementBtn) {
    calculatePlacementBtn.addEventListener('click', async () => {
      try {
        // Show loading state
        calculatePlacementBtn.disabled = true;
        calculatePlacementBtn.textContent = 'Calculating...';
        
        // Get items and containers
        const itemsResponse = await fetch('/items');
        const containersResponse = await fetch('/containers');
        
        if (!itemsResponse.ok || !containersResponse.ok) {
          throw new Error('Failed to fetch data');
        }
        
        const items = await itemsResponse.json();
        const containers = await containersResponse.json();
        
        // Filter unplaced items
        const unplacedItems = items.filter(item => !item.currentLocation);
        
        if (unplacedItems.length === 0) {
          alert('No items need placement');
          return;
        }
        
        // Call placement API
        const placementResponse = await fetch('/calculate-placement', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            items: unplacedItems,
            containers: containers
          })
        });
        
        if (!placementResponse.ok) {
          throw new Error('Placement calculation failed');
        }
        
        const placementResult = await placementResponse.json();
        
        // Show results
        alert(`Placement calculated: ${placementResult.placements.length} items placed with ${placementResult.rearrangements.length} rearrangements needed.`);
        
        // Reload data
        loadItems();
        loadContainers();
      } catch (error) {
        console.error('Placement error:', error);
        alert(`Placement error: ${error.message}`);
      } finally {
        // Reset button state
        calculatePlacementBtn.disabled = false;
        calculatePlacementBtn.textContent = 'Calculate Optimal Placement';
      }
    });
  }
  
  // Search functionality
  const searchItemBtn = document.getElementById('searchItemBtn');
  const searchInput = document.getElementById('searchInput');
  
  if (searchItemBtn && searchInput) {
    searchItemBtn.addEventListener('click', async () => {
      const searchTerm = searchInput.value.trim();
      if (!searchTerm) return;
      
      try {
        // Call search API
        const searchResponse = await fetch(`/search-item?${searchTerm.match(/^\d+$/) ? 'itemId' : 'itemName'}=${encodeURIComponent(searchTerm)}`);
        
        if (!searchResponse.ok) {
          throw new Error('Search failed');
        }
        
        const searchResults = await searchResponse.json();
        displaySearchResults(searchResults);
      } catch (error) {
        console.error('Search error:', error);
        alert(`Search error: ${error.message}`);
      }
    });
    
    // Also search on Enter key
    searchInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        searchItemBtn.click();
      }
    });
  }
  
  function displaySearchResults(results) {
    const searchResultsElement = document.getElementById('searchResults');
    if (!searchResultsElement) return;
    
    searchResultsElement.innerHTML = '';
    
    if (results.length === 0) {
      searchResultsElement.innerHTML = '<p class="text-center">No items found</p>';
      return;
    }
    
    results.forEach(result => {
      const resultItem = document.createElement('button');
      resultItem.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center';
      resultItem.innerHTML = `
        <div>
          <strong>${result.itemId}</strong>: ${result.name}
          <small class="d-block text-muted">Location: ${result.containerId || 'Not placed'}</small>
        </div>
        <span class="badge bg-primary rounded-pill">${result.retrievalSteps || 0} steps</span>
      `;
      
      resultItem.addEventListener('click', () => {
        displayItemLocation(result);
      });
      
      searchResultsElement.appendChild(resultItem);
    });
  }
  
  function displayItemLocation(itemLocation) {
    // Show the item in 3D viewer
    if (itemLocationViewerInstance) {
      // Clear previous container and items
      itemLocationViewerInstance.cleanup();
      
      // Get container data
      fetch(`/api/containers?containerId=${itemLocation.containerId}`)
        .then(response => response.json())
        .then(containers => {
          if (containers.length > 0) {
            const container = containers[0];
            
            // Create container in viewer
            itemLocationViewerInstance.createContainers([container]);
            
            // Add the item to viewer
            itemLocationViewerInstance.updateItems([{
              id: itemLocation.itemId,
              name: itemLocation.name,
              position: itemLocation.position,
              dimensions: itemLocation.rotation,
              priority: 100, // Highlight the item
              containerId: itemLocation.containerId
            }]);
          }
        })
        .catch(error => console.error('Error loading container for item location:', error));
    }
    
    // Display retrieval steps
    const retrievalStepsElement = document.getElementById('retrievalSteps');
    if (retrievalStepsElement) {
      // Get retrieval steps from API
      fetch(`/api/items/retrieve`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          itemId: itemLocation.itemId,
          userId: 'user1' // Default user
        })
      })
        .then(response => response.json())
        .then(retrievalData => {
          if (retrievalData.steps && retrievalData.steps.length > 0) {
            let stepsHtml = '<ol class="list-group list-group-numbered">';
            retrievalData.steps.forEach(step => {
              stepsHtml += `<li class="list-group-item">${step.action}: ${step.itemId}</li>`;
            });
            stepsHtml += '</ol>';
            retrievalStepsElement.innerHTML = stepsHtml;
          } else {
            retrievalStepsElement.innerHTML = '<p class="text-center">No retrieval steps needed</p>';
          }
        })
        .catch(error => {
          console.error('Error getting retrieval steps:', error);
          retrievalStepsElement.innerHTML = '<p class="text-center text-danger">Error getting retrieval steps</p>';
        });
    }
  }
  
  // Waste management
  const identifyWasteBtn = document.getElementById('identifyWasteBtn');
  if (identifyWasteBtn) {
    identifyWasteBtn.addEventListener('click', async () => {
      try {
        const response = await fetch('/api/waste/identify');
        if (!response.ok) {
          throw new Error('Failed to identify waste');
        }
        
        const wasteItems = await response.json();
        displayWasteItems(wasteItems);
      } catch (error) {
        console.error('Waste identification error:', error);
        alert(`Error identifying waste: ${error.message}`);
      }
    });
  }
  
  function displayWasteItems(wasteItems) {
    const wasteItemsList = document.getElementById('wasteItemsList');
    if (!wasteItemsList) return;
    
    wasteItemsList.innerHTML = '';
    
    if (wasteItems.length === 0) {
      wasteItemsList.innerHTML = '<p class="text-center">No waste items identified</p>';
      return;
    }
    
    let wasteHtml = '<div class="list-group">';
    wasteItems.forEach(item => {
      wasteHtml += `
        <div class="list-group-item">
          <div class="d-flex w-100 justify-content-between">
            <h5 class="mb-1">${item.itemId}: ${item.name}</h5>
            <small>${item.reason}</small>
          </div>
          <p class="mb-1">Location: ${item.containerId || 'Not placed'}</p>
          <small>Mass: ${item.mass}kg</small>
        </div>
      `;
    });
    wasteHtml += '</div>';
    
    wasteItemsList.innerHTML = wasteHtml;
  }
  
  const planWasteReturnBtn = document.getElementById('planWasteReturnBtn');
  if (planWasteReturnBtn) {
    planWasteReturnBtn.addEventListener('click', async () => {
      const undockingContainerId = document.getElementById('undockingContainerId').value.trim();
      const maxWeight = document.getElementById('maxWeight').value;
      
      if (!undockingContainerId || !maxWeight) {
        alert('Please enter both container ID and max weight');
        return;
      }
      
      try {
        const response = await fetch('/api/waste/return-plan', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            undockingContainerId,
            maxWeight: parseFloat(maxWeight)
          })
        });
        
        if (!response.ok) {
          throw new Error('Failed to generate waste return plan');
        }
        
        const returnPlan = await response.json();
        displayWasteReturnPlan(returnPlan);
      } catch (error) {
        console.error('Waste return plan error:', error);
        alert(`Error generating waste return plan: ${error.message}`);
      }
    });
  }
  
  function displayWasteReturnPlan(returnPlan) {
    const wasteReturnPlan = document.getElementById('wasteReturnPlan');
    if (!wasteReturnPlan) return;
    
    if (!returnPlan.steps || returnPlan.steps.length === 0) {
      wasteReturnPlan.innerHTML = '<p class="text-center">No steps needed for waste return</p>';
      return;
    }
    
    let planHtml = `
      <div class="alert alert-info">
        Total waste items: ${returnPlan.totalItems || 'unknown'}
        Total weight: ${returnPlan.totalWeight || 'unknown'}kg
      </div>
      <ol class="list-group list-group-numbered">
    `;
    
    returnPlan.steps.forEach(step => {
      planHtml += `
        <li class="list-group-item">
          ${step.action} ${step.itemId}
          ${step.fromContainer ? 'from ' + step.fromContainer : ''}
          ${step.toContainer ? 'to ' + step.toContainer : ''}
        </li>
      `;
    });
    
    planHtml += '</ol>';
    wasteReturnPlan.innerHTML = planHtml;
  }
  
  // Simulation
  const simulateTimeBtn = document.getElementById('simulateTimeBtn');
  if (simulateTimeBtn) {
    simulateTimeBtn.addEventListener('click', async () => {
      const days = document.getElementById('simulateDays').value;
      if (!days || isNaN(days) || days < 1) {
        alert('Please enter a valid number of days');
        return;
      }
      
      try {
        // Get selected items
        const selectedItems = [];
        document.querySelectorAll('#simulationItemsList .form-check-input:checked').forEach(checkbox => {
          selectedItems.push(checkbox.value);
        });
        
        const response = await fetch('/api/simulation/days', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            numOfDays: parseInt(days),
            itemsToBeUsedPerDay: selectedItems
          })
        });
        
        if (!response.ok) {
          throw new Error('Failed to simulate time');
        }
        
        const results = await response.json();
        displaySimulationResults(results);
        
        // Update date display
        if (currentDateDisplay && results.currentDate) {
          currentDateDisplay.textContent = new Date(results.currentDate).toISOString().split('T')[0];
        }
      } catch (error) {
        console.error('Simulation error:', error);
        alert(`Error simulating time: ${error.message}`);
      }
    });
  }
  
  function displaySimulationResults(results) {
    const simulationResults = document.getElementById('simulationResults');
    if (!simulationResults) return;
    
    let resultsHtml = `
      <div class="alert alert-success">
        Time advanced by ${results.daysSimulated || 'unknown'} days
      </div>
    `;
    
    if (results.usedItems && results.usedItems.length > 0) {
      resultsHtml += `
        <h5>Items Used:</h5>
        <ul class="list-group mb-3">
      `;
      
      results.usedItems.forEach(item => {
        resultsHtml += `<li class="list-group-item">${item.itemId}: ${item.name}</li>`;
      });
      
      resultsHtml += '</ul>';
    }
    
    if (results.expiredItems && results.expiredItems.length > 0) {
      resultsHtml += `
        <h5>Items Expired:</h5>
        <ul class="list-group mb-3">
      `;
      
      results.expiredItems.forEach(item => {
        resultsHtml += `<li class="list-group-item">${item.itemId}: ${item.name}</li>`;
      });
      
      resultsHtml += '</ul>';
    }
    
    simulationResults.innerHTML = resultsHtml;
  }
  
  // Quick action buttons
  const quickPlacementBtn = document.getElementById('quickPlacementBtn');
  if (quickPlacementBtn) {
    quickPlacementBtn.addEventListener('click', () => {
      document.getElementById('itemsBtn').click();
      if (calculatePlacementBtn) {
        calculatePlacementBtn.click();
      }
    });
  }
  
  const quickSearchBtn = document.getElementById('quickSearchBtn');
  if (quickSearchBtn) {
    quickSearchBtn.addEventListener('click', () => {
      document.getElementById('searchBtn').click();
    });
  }
  
  const quickWasteBtn = document.getElementById('quickWasteBtn');
  if (quickWasteBtn) {
    quickWasteBtn.addEventListener('click', () => {
      document.getElementById('wasteBtn').click();
      if (identifyWasteBtn) {
        identifyWasteBtn.click();
      }
    });
  }

  // Initialize the data on load for home tab
  const homeDateDisplay = document.getElementById('homeDateDisplay');
  if (homeDateDisplay) {
    homeDateDisplay.textContent = new Date().toLocaleDateString('en-US', {
      weekday: 'long',
      year: 'numeric', 
      month: 'long', 
      day: 'numeric'
    });
  }
  
  // Load container utilization stats for home tab
  const containerUtilizationChart = document.getElementById('containerUtilizationChart');
  if (containerUtilizationChart) {
    loadContainerUtilization();
  }
  
  async function loadContainerUtilization() {
    try {
      const containers = await loadContainers();
      if (containers.length === 0) {
        containerUtilizationChart.innerHTML = '<p class="text-muted">No containers available</p>';
        return;
      }
      
      let chartHtml = '';
      containers.forEach(container => {
        const totalVolume = container.width * container.depth * container.height;
        const usagePercent = container.occupiedSpace > 0 
          ? Math.round((container.occupiedSpace / totalVolume) * 100) 
          : 0;
        
        chartHtml += `
          <div class="utilization-item">
            <span class="container-id">${container.containerId}</span>
            <div class="bar-container">
              <div class="bar bg-${usagePercent > 80 ? 'danger' : 'success'}" style="width: ${usagePercent}%"></div>
            </div>
            <span class="percent">${usagePercent}%</span>
          </div>
        `;
      });
      
      containerUtilizationChart.innerHTML = chartHtml;
    } catch (error) {
      console.error('Error loading container utilization:', error);
      containerUtilizationChart.innerHTML = '<p class="text-danger">Error loading container data</p>';
    }
  }
  
  // Load recent activities
  const recentActivities = document.getElementById('recentActivities');
  if (recentActivities) {
    loadRecentActivities();
  }
  
  async function loadRecentActivities() {
    try {
      const logs = await loadLogs();
      if (logs.length === 0) {
        recentActivities.innerHTML = '<p class="text-muted">No recent activities</p>';
        return;
      }
      
      let activitiesHtml = '<ul class="list-group">';
      // Show only the most recent 5 logs
      const recentLogs = logs.slice(0, 5);
      
      recentLogs.forEach(log => {
        const timestamp = new Date(log.timestamp);
        const timeAgo = getTimeAgo(timestamp);
        
        activitiesHtml += `
          <li class="list-group-item">
            <div class="d-flex w-100 justify-content-between">
              <span>${log.action}</span>
              <small>${timeAgo}</small>
            </div>
            <small>${log.user}</small>
          </li>
        `;
      });
      
      activitiesHtml += '</ul>';
      recentActivities.innerHTML = activitiesHtml;
    } catch (error) {
      console.error('Error loading recent activities:', error);
      recentActivities.innerHTML = '<p class="text-danger">Error loading activity data</p>';
    }
  }
  
  // Helper function to format time ago
  function getTimeAgo(timestamp) {
    const now = new Date();
    const diff = Math.floor((now - timestamp) / 1000); // Difference in seconds
    
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)} days ago`;
    
    return new Date(timestamp).toLocaleDateString();
  }

  // Load the data on page load
  loadContainers();
  loadItems();
  loadLogs();
  
  // Automatically select the Home tab on page load
  document.getElementById('homeBtn').click();
});
