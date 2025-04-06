import os
import json
import csv
import io
import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.middleware.proxy_fix import ProxyFix

from services.placement import PlacementService
from services.retrieval import RetrievalService
from services.waste import WasteService
from services.simulation import SimulationService
from models.item import Item
from models.container import Container
from models.placement import ItemPlacement, RearrangementStep, WasteItem, WasteReturnStep, PlacementRequest, PlacementResponse

app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "space-station-dev-key")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Data storage
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CONTAINERS_FILE = DATA_DIR / "containers.json"
ITEMS_FILE = DATA_DIR / "items.json"
LOGS_FILE = DATA_DIR / "logs.json"

# Initialize with empty data if files don't exist
if not CONTAINERS_FILE.exists():
    with open(CONTAINERS_FILE, 'w') as f:
        json.dump([], f)

if not ITEMS_FILE.exists():
    with open(ITEMS_FILE, 'w') as f:
        json.dump([], f)

if not LOGS_FILE.exists():
    with open(LOGS_FILE, 'w') as f:
        json.dump([], f)

# Initialize service classes
placement_service = PlacementService()
retrieval_service = RetrievalService()
waste_service = WasteService()
simulation_service = SimulationService()

# Current date for simulation purposes
CURRENT_DATE = datetime.datetime.now()

# Helper function to save data to files
def save_data():
    """Save all data to files"""
    # This function ensures we properly save all data to the JSON files
    
    # Get the current items and containers
    items_list = []
    containers_list = []
    
    # First, load any existing data
    if ITEMS_FILE.exists():
        with open(ITEMS_FILE, 'r') as f:
            try:
                items_list = json.load(f)
            except json.JSONDecodeError:
                print(f"Error reading {ITEMS_FILE}, initializing with empty list")
                items_list = []
    
    if CONTAINERS_FILE.exists():
        with open(CONTAINERS_FILE, 'r') as f:
            try:
                containers_list = json.load(f)
            except json.JSONDecodeError:
                print(f"Error reading {CONTAINERS_FILE}, initializing with empty list")
                containers_list = []
    
    # Write back to ensure files exist and are valid JSON
    with open(ITEMS_FILE, 'w') as f:
        json.dump(items_list, f, indent=2)
    
    with open(CONTAINERS_FILE, 'w') as f:
        json.dump(containers_list, f, indent=2)

# Helper function to convert dict to Item object
def dict_to_item(item_dict: Dict) -> Item:
    """Convert a dictionary to an Item object"""
    item = Item(
        itemId=item_dict["itemId"],
        name=item_dict["name"],
        width=item_dict["width"],
        depth=item_dict["depth"],
        height=item_dict["height"],
        mass=item_dict["mass"],
        priority=item_dict["priority"],
        expiryDate=item_dict["expiryDate"],
        usageLimit=item_dict["usageLimit"],
        preferredZone=item_dict["preferredZone"]
    )
    item.isWaste = item_dict.get("isWaste", False)
    item.currentLocation = item_dict.get("currentLocation")
    return item

# Helper function to convert dict to Container object
def dict_to_container(container_dict: Dict) -> Container:
    """Convert a dictionary to a Container object"""
    container = Container(
        containerId=container_dict["containerId"],
        zone=container_dict["zone"],
        width=container_dict["width"],
        depth=container_dict["depth"],
        height=container_dict["height"]
    )
    container.occupiedSpace = container_dict.get("occupiedSpace", 0)
    container.items = container_dict.get("items", [])
    return container

# Helper function to add a log entry
def add_log(action: str, details: Optional[Dict[str, Any]] = None, user: str = "system", item_id: Optional[str] = None):
    """Add a log entry with the current timestamp
    
    This is a wrapper around the LoggingService for backward compatibility.
    It ensures all application logs are properly recorded in a standardized format.
    
    Args:
        action: Type of action performed
        details: Additional details about the action
        user: ID of the user who performed the action
        item_id: ID of the item involved (if applicable)
        
    Returns:
        The created log entry
    """
    if details is None:
        details = {}
    
    # Add current date for tracking simulation time
    if not details.get("currentDate") and CURRENT_DATE:
        details["currentDate"] = CURRENT_DATE.isoformat()
        
    # Use the enhanced logging service
    from services.logging_service import LoggingService
    logging_service = LoggingService()
    
    # Map old parameters to new format
    return logging_service.add_log(
        action=action,
        details=details,
        user_id=user,
        item_id=item_id
    )

# Routes
@app.route('/')
def get_index():
    """Main application page"""
    return render_template('index.html')

@app.route('/static/<path:path>')
def send_static(path):
    """Serve static files"""
    return send_from_directory('static', path)

@app.route('/api/placement/recommend', methods=['POST'])
def calculate_placement():
    """Calculate optimal placement for items"""
    data = request.json
    
    # Load existing containers and items if not provided
    containers_data = data.get('containers', [])
    items_data = data.get('items', [])
    
    if not containers_data:
        if CONTAINERS_FILE.exists():
            with open(CONTAINERS_FILE, 'r') as f:
                containers_data = json.load(f)
    
    if not items_data:
        if ITEMS_FILE.exists():
            with open(ITEMS_FILE, 'r') as f:
                items_data = json.load(f)
    
    # Convert dictionaries to model objects
    containers = [dict_to_container(c) for c in containers_data]
    items = [dict_to_item(i) for i in items_data]
    
    # Use the placement service to calculate placements
    # Convert items and containers from lists to dictionaries for the service
    items_dict = {item.itemId: item for item in items}
    containers_dict = {container.containerId: container for container in containers}
    
    # Call the placement service
    placement_response = placement_service.calculate_placement(
        items=items_dict,
        containers=containers_dict
    )
    
    # Extract placements and rearrangements from the response
    placements = placement_response.placements
    rearrangements = placement_response.rearrangements
    
    # Update item locations based on placements
    for placement in placements:
        # Find the corresponding item
        item_idx = next((i for i, item in enumerate(items_data) 
                       if item['itemId'] == placement.itemId), None)
        
        if item_idx is not None:
            # Update item's location
            items_data[item_idx]['currentLocation'] = {
                "containerId": placement.containerId,
                "position": placement.position,
                "rotation": placement.rotation
            }
            
            # Find the corresponding container
            container_idx = next((i for i, container in enumerate(containers_data) 
                                if container['containerId'] == placement.containerId), None)
            
            if container_idx is not None:
                # Add item to container's items list if not already there
                if placement.itemId not in containers_data[container_idx]['items']:
                    containers_data[container_idx]['items'].append(placement.itemId)
                
                # Update container's occupied space
                item = next((item for item in items if item.itemId == placement.itemId), None)
                if item:
                    volume = item.get_volume()
                    containers_data[container_idx]['occupiedSpace'] += volume
    
    # Save updated data
    with open(ITEMS_FILE, 'w') as f:
        json.dump(items_data, f, indent=2)
    
    with open(CONTAINERS_FILE, 'w') as f:
        json.dump(containers_data, f, indent=2)
    
    # Log the placement operation
    add_log(
        action="calculate_placement",
        details={
            "numItems": len(items),
            "numPlacements": len(placements),
            "numRearrangements": len(rearrangements)
        }
    )
    
    # Convert model objects back to dictionaries for JSON response
    placements_dict = [
        {
            "itemId": p.itemId,
            "containerId": p.containerId,
            "position": p.position,
            "rotation": p.rotation
        } for p in placements
    ]
    
    rearrangements_dict = [
        {
            "step": r.step,
            "action": r.action,
            "itemId": r.itemId,
            "fromContainer": r.fromContainer,
            "toContainer": r.toContainer,
            "position": r.position
        } for r in rearrangements
    ]
    
    return jsonify({
        "placements": placements_dict,
        "rearrangements": rearrangements_dict
    })

@app.route('/api/items/search')
def search_item():
    """Search for an item by ID or name"""
    item_id = request.args.get('itemId')
    item_name = request.args.get('itemName')
    user_id = request.args.get('userId', 'anonymous')
    
    # Add a log for the search
    add_log(
        action="search_item",
        details={"itemId": item_id, "itemName": item_name},
        user=user_id
    )
    
    # Load items data
    items = []
    if ITEMS_FILE.exists():
        with open(ITEMS_FILE, 'r') as f:
            items = json.load(f)
    
    # Perform the search
    results = []
    if item_id:
        results = [item for item in items if item['itemId'] == item_id]
    elif item_name:
        # Case-insensitive partial match
        search_term = item_name.lower()
        results = [item for item in items if search_term in item['name'].lower()]
    
    return jsonify(results)

@app.route('/api/items/retrieve', methods=['POST'])
def retrieve_item():
    """Get item location and retrieval steps"""
    data = request.json
    item_id = data.get('itemId')
    user_id = data.get('userId', 'anonymous')
    
    if not item_id:
        return jsonify({"error": "No item ID provided"}), 400
    
    # Load items and containers data
    items_data = {}
    containers_data = {}
    
    if ITEMS_FILE.exists():
        with open(ITEMS_FILE, 'r') as f:
            items_list = json.load(f)
            items_data = {item['itemId']: dict_to_item(item) for item in items_list}
    
    if CONTAINERS_FILE.exists():
        with open(CONTAINERS_FILE, 'r') as f:
            containers_list = json.load(f)
            containers_data = {container['containerId']: dict_to_container(container) for container in containers_list}
    
    # Find the requested item
    if item_id not in items_data:
        return jsonify({"error": f"Item {item_id} not found"}), 404
    
    item = items_data[item_id]
    items_list = []
    
    if ITEMS_FILE.exists():
        with open(ITEMS_FILE, 'r') as f:
            items_list = json.load(f)
    
    try:
        # Get item location details
        item_location = retrieval_service.get_item_location(
            item_id=item_id,
            items=items_data,
            containers=containers_data
        )
        
        # Retrieve item and get retrieval steps
        success, retrieval_steps = retrieval_service.retrieve_item(
            item_id=item_id,
            user_id=user_id,
            items=items_data,
            containers=containers_data
        )
        
        # Check if we were able to get location info
        if not item_location:
            return jsonify({"error": "Unable to locate item"}), 404
            
        # Log the retrieval operation
        add_log(
            action="retrieve_item",
            details={
                "itemId": item_id,
                "containerId": item_location.containerId,
                "numSteps": len(retrieval_steps) if isinstance(retrieval_steps, list) else 0
            },
            user=user_id
        )
        
        # The retrieval operation has already updated the usage count in the service
        
        # Convert updated data back to the items list for saving
        updated_items_list = []
        for old_item_dict in items_list:
            item_id = old_item_dict['itemId']
            if item_id in items_data:
                # Convert from Item object back to dict
                updated_item = items_data[item_id]
                updated_dict = {
                    "itemId": updated_item.itemId,
                    "name": updated_item.name,
                    "width": updated_item.width,
                    "depth": updated_item.depth,
                    "height": updated_item.height,
                    "mass": updated_item.mass,
                    "priority": updated_item.priority,
                    "expiryDate": updated_item.expiryDate,
                    "usageLimit": updated_item.usageLimit,
                    "preferredZone": updated_item.preferredZone,
                    "isWaste": updated_item.isWaste,
                    "currentLocation": updated_item.currentLocation
                }
                updated_items_list.append(updated_dict)
            else:
                updated_items_list.append(old_item_dict)
        
        # Save updated items data
        with open(ITEMS_FILE, 'w') as f:
            json.dump(updated_items_list, f, indent=2)
            
        # Update containers data as well
        containers_list = []
        if CONTAINERS_FILE.exists():
            with open(CONTAINERS_FILE, 'r') as f:
                containers_list = json.load(f)
                
        updated_containers_list = []
        for old_container_dict in containers_list:
            container_id = old_container_dict['containerId']
            if container_id in containers_data:
                # Convert from Container object back to dict
                updated_container = containers_data[container_id]
                updated_dict = {
                    "containerId": updated_container.containerId,
                    "zone": updated_container.zone,
                    "width": updated_container.width,
                    "depth": updated_container.depth,
                    "height": updated_container.height,
                    "occupiedSpace": updated_container.occupiedSpace,
                    "items": updated_container.items
                }
                updated_containers_list.append(updated_dict)
            else:
                updated_containers_list.append(old_container_dict)
                
        # Save updated containers data
        with open(CONTAINERS_FILE, 'w') as f:
            json.dump(updated_containers_list, f, indent=2)
        
        # Convert model objects to dictionaries for JSON response
        item_location_dict = {
            "itemId": item_location.itemId,
            "name": item_location.name,
            "containerId": item_location.containerId,
            "position": item_location.position,
            "rotation": item_location.rotation,
            "retrievalSteps": item_location.retrievalSteps,
            "blockedBy": item_location.blockedBy
        }
        
        # Convert retrieval steps to dict format
        retrieval_steps_dict = []
        if isinstance(retrieval_steps, list):
            for step in retrieval_steps:
                if isinstance(step, dict):
                    retrieval_steps_dict.append(step)
                else:
                    # Assume it's a step object with attributes
                    try:
                        step_dict = {
                            "step": step.get("step", 0) if isinstance(step, dict) else getattr(step, "step", 0),
                            "action": step.get("action", "") if isinstance(step, dict) else getattr(step, "action", ""),
                            "itemId": step.get("itemId", "") if isinstance(step, dict) else getattr(step, "itemId", ""),
                        }
                        
                        # Add optional fields if they exist
                        if hasattr(step, "fromContainer") or (isinstance(step, dict) and "fromContainer" in step):
                            step_dict["fromContainer"] = step.get("fromContainer") if isinstance(step, dict) else getattr(step, "fromContainer", None)
                            
                        if hasattr(step, "toContainer") or (isinstance(step, dict) and "toContainer" in step):
                            step_dict["toContainer"] = step.get("toContainer") if isinstance(step, dict) else getattr(step, "toContainer", None)
                            
                        if hasattr(step, "position") or (isinstance(step, dict) and "position" in step):
                            step_dict["position"] = step.get("position") if isinstance(step, dict) else getattr(step, "position", None)
                            
                        retrieval_steps_dict.append(step_dict)
                    except Exception as e:
                        print(f"Error converting step: {e}")
                        # Add a basic version of the step
                        retrieval_steps_dict.append({"step": len(retrieval_steps_dict) + 1, "error": str(e)})
        
        return jsonify({
            "itemLocation": item_location_dict,
            "retrievalSteps": retrieval_steps_dict
        })
    
    except Exception as e:
        return jsonify({
            "error": str(e),
            "itemLocation": None,
            "retrievalSteps": []
        }), 500

@app.route('/api/simulate/day', methods=['POST'])
def simulate_days():
    """Simulate the passage of time"""
    data = request.json
    days = data.get('numOfDays', 1)
    to_timestamp = data.get('toTimestamp')
    items_to_use = data.get('itemsToBeUsedPerDay', [])
    
    # Load items data
    items_list = []
    if ITEMS_FILE.exists():
        with open(ITEMS_FILE, 'r') as f:
            items_list = json.load(f)
    
    # Convert items to dictionary format for easier access
    items_data = {item['itemId']: dict_to_item(item) for item in items_list}
    
    # Simulate usage of specified items
    for item_id in items_to_use:
        if item_id in items_data and items_data[item_id].usageLimit > 0:
            items_data[item_id].usageLimit -= 1
            
            # Update the item in items_list
            for i, item_dict in enumerate(items_list):
                if item_dict['itemId'] == item_id:
                    items_list[i]['usageLimit'] = items_data[item_id].usageLimit
                    
                    # Mark as waste if no uses left
                    if items_data[item_id].usageLimit <= 0:
                        items_list[i]['isWaste'] = True
                    
                    break
    
    # Simulate time passage
    global CURRENT_DATE
    old_date = CURRENT_DATE
    
    # Calculate days based on to_timestamp if provided
    if to_timestamp:
        try:
            target_date = datetime.datetime.fromisoformat(to_timestamp)
            days = (target_date - CURRENT_DATE).days
            days = max(1, days)  # Ensure at least 1 day passes
        except (ValueError, TypeError):
            # If the timestamp is invalid, use the provided numOfDays
            pass
    
    new_date, updated_items, waste_items = simulation_service.simulate_days(
        num_days=days,
        current_date=CURRENT_DATE,
        items=items_data
    )
    CURRENT_DATE = new_date
    
    # Update items data with simulation results
    for item_id, item in updated_items.items():
        for i, item_dict in enumerate(items_list):
            if item_dict['itemId'] == item_id:
                items_list[i]['isWaste'] = item.isWaste
                break
    
    # Save updated items data
    with open(ITEMS_FILE, 'w') as f:
        json.dump(items_list, f, indent=2)
    
    # Convert waste items to dictionary format for response
    waste_items_dict = [
        {
            "itemId": w.itemId,
            "name": w.name,
            "reason": w.reason,
            "containerId": w.containerId,
            "position": w.position,
            "mass": w.mass
        } for w in waste_items
    ]
    
    # Separate expired items from usage-depleted items
    expiring_items = [w for w in waste_items_dict if w['reason'] == 'Expired']
    usage_depleted_items = [w for w in waste_items_dict if w['reason'] == 'Out of Uses']
    
    # Add a log for the simulation
    add_log(
        action="simulate_days",
        details={
            "days": days,
            "oldDate": old_date.isoformat(),
            "newDate": new_date.isoformat(),
            "numExpiringItems": len(expiring_items),
            "numUsageDepletedItems": len(usage_depleted_items),
            "itemsUsed": items_to_use
        }
    )
    
    return jsonify({
        "oldDate": old_date.isoformat(),
        "newDate": new_date.isoformat(),
        "expiringItems": expiring_items,
        "usageDepletedItems": usage_depleted_items
    })

@app.route('/api/waste/identify')
def identify_waste():
    """Identify waste items (expired or used up)"""
    # Load items and containers data
    items_list = []
    containers_list = []
    
    if ITEMS_FILE.exists():
        with open(ITEMS_FILE, 'r') as f:
            items_list = json.load(f)
    
    if CONTAINERS_FILE.exists():
        with open(CONTAINERS_FILE, 'r') as f:
            containers_list = json.load(f)
    
    # Convert to dictionaries for easier access
    items_data = {item['itemId']: dict_to_item(item) for item in items_list}
    containers_data = {container['containerId']: dict_to_container(container) for container in containers_list}
    
    # Identify waste items
    waste_items, total_mass, return_steps = waste_service.identify_waste_items(
        items=items_data,
        containers=containers_data,
        current_date=CURRENT_DATE
    )
    
    # Update items data with waste status
    for waste_item in waste_items:
        for i, item_dict in enumerate(items_list):
            if item_dict['itemId'] == waste_item.itemId:
                items_list[i]['isWaste'] = True
                break
    
    # Save updated items data
    with open(ITEMS_FILE, 'w') as f:
        json.dump(items_list, f, indent=2)
    
    # Convert waste items and return steps to dictionary format for response
    waste_items_dict = [
        {
            "itemId": w.itemId,
            "name": w.name,
            "reason": w.reason,
            "containerId": w.containerId,
            "position": w.position,
            "mass": w.mass
        } for w in waste_items
    ]
    
    return_steps_dict = [
        {
            "step": step.step,
            "action": step.action,
            "itemId": step.itemId,
            "fromContainer": step.fromContainer,
            "toContainer": step.toContainer
        } for step in return_steps
    ]
    
    # Add a log for the waste identification
    add_log(
        action="identify_waste",
        details={
            "numWasteItems": len(waste_items),
            "totalMass": total_mass,
            "numReturnSteps": len(return_steps)
        }
    )
    
    return jsonify({
        "wasteItems": waste_items_dict,
        "totalMass": total_mass,
        "returnSteps": return_steps_dict
    })

@app.route('/api/waste/return-plan', methods=['POST'])
def waste_return_plan():
    """Generate a waste return plan for undocking"""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "Invalid request data"}), 400
    
    undocking_container_id = data.get('undockingContainerId')
    undocking_date = data.get('undockingDate')
    max_weight = data.get('maxWeight', 100.0)  # Default to 100kg if not specified
    
    if not undocking_container_id:
        return jsonify({"success": False, "error": "Undocking container ID is required"}), 400
    
    # Load items and containers data
    items_list = []
    containers_list = []
    
    if ITEMS_FILE.exists():
        with open(ITEMS_FILE, 'r') as f:
            items_list = json.load(f)
    
    if CONTAINERS_FILE.exists():
        with open(CONTAINERS_FILE, 'r') as f:
            containers_list = json.load(f)
    
    # Convert to dictionaries for easier access
    items_data = {item['itemId']: dict_to_item(item) for item in items_list}
    containers_data = {container['containerId']: dict_to_container(container) for container in containers_list}
    
    try:
        # First identify all waste items
        waste_items, total_mass, _ = waste_service.identify_waste_items(
            items=items_data,
            containers=containers_data,
            current_date=CURRENT_DATE
        )
        
        # Generate return plan
        return_steps = waste_service.generate_waste_return_plan(
            waste_items=waste_items,
            max_weight=float(max_weight),
            undocking_container_id=undocking_container_id
        )
        
        # Select items that are in the return plan
        return_items = []
        total_volume = 0.0
        total_weight = 0.0
        
        # Get items that will be returned
        item_ids_in_plan = set()
        for step in return_steps:
            item_id = step.itemId
            if item_id in items_data and item_id not in item_ids_in_plan:
                item = items_data[item_id]
                item_ids_in_plan.add(item_id)
                
                # Find the matching waste item
                waste_item = next((w for w in waste_items if w.itemId == item_id), None)
                
                if waste_item:
                    return_items.append({
                        "itemId": item_id,
                        "name": item.name,
                        "reason": waste_item.reason
                    })
                    
                    # Add weight and calculate volume
                    item_volume = item.width * item.depth * item.height
                    total_volume += item_volume
                    total_weight += item.mass
        
        # Create return manifest
        return_manifest = {
            "undockingContainerId": undocking_container_id,
            "undockingDate": undocking_date or CURRENT_DATE.isoformat(),
            "returnItems": return_items,
            "totalVolume": total_volume,
            "totalWeight": total_weight
        }
        
        # Format the return steps for the response
        formatted_steps = []
        for i, step in enumerate(return_steps):
            formatted_step = {
                "step": i + 1,
                "itemId": step.itemId,
                "itemName": items_data[step.itemId].name if step.itemId in items_data else "Unknown",
                "fromContainer": step.fromContainer,
                "toContainer": step.toContainer
            }
            formatted_steps.append(formatted_step)
        
        # Add retrieval steps (simplify by reusing steps for now)
        retrieval_steps = [
            {
                "step": i + 1,
                "action": "retrieve" if step.action == "move" else step.action,
                "itemId": step.itemId,
                "itemName": items_data[step.itemId].name if step.itemId in items_data else "Unknown"
            }
            for i, step in enumerate(return_steps)
        ]
        
        # Add a log for the waste return plan
        add_log(
            action="waste_return_plan",
            details={
                "undockingContainerId": undocking_container_id,
                "maxWeight": max_weight,
                "itemsSelected": len(return_items),
                "totalWeight": total_weight,
                "totalVolume": total_volume
            }
        )
        
        return jsonify({
            "success": True,
            "returnPlan": formatted_steps,
            "retrievalSteps": retrieval_steps,
            "returnManifest": return_manifest
        })
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in waste_return_plan: {error_message}")
        return jsonify({"success": False, "error": error_message}), 500

@app.route('/api/waste/complete-undocking', methods=['POST'])
def complete_undocking():
    """Mark waste items as officially removed from the system"""
    data = request.json
    if not data:
        return jsonify({"success": False, "error": "Invalid request data"}), 400
    
    undocking_container_id = data.get('undockingContainerId')
    timestamp = data.get('timestamp')
    
    if not undocking_container_id:
        return jsonify({"success": False, "error": "Undocking container ID is required"}), 400
    
    # Load items and containers data
    items_list = []
    containers_list = []
    
    if ITEMS_FILE.exists():
        with open(ITEMS_FILE, 'r') as f:
            items_list = json.load(f)
    
    if CONTAINERS_FILE.exists():
        with open(CONTAINERS_FILE, 'r') as f:
            containers_list = json.load(f)
    
    # Convert to dictionaries for easier access
    items_data = {item['itemId']: dict_to_item(item) for item in items_list}
    containers_data = {container['containerId']: dict_to_container(container) for container in containers_list}
    
    try:
        # Identify all waste items
        waste_items, _, _ = waste_service.identify_waste_items(
            items=items_data,
            containers=containers_data,
            current_date=CURRENT_DATE
        )
        
        # Count items removed
        items_removed = 0
        
        # Items to remove from the system
        items_to_remove = []
        
        # Remove waste items from the system
        for waste_item in waste_items:
            item_id = waste_item.itemId
            
            # Only remove items that are in the undocking container
            if waste_item.containerId == undocking_container_id:
                items_to_remove.append(item_id)
                
                # Remove from container's items list if it exists
                for container in containers_list:
                    if container['containerId'] == waste_item.containerId and item_id in container.get('items', []):
                        container['items'].remove(item_id)
                        
                        # Update container's occupied space
                        for item in items_list:
                            if item['itemId'] == item_id:
                                item_volume = item['width'] * item['depth'] * item['height']
                                container['occupiedSpace'] = max(0, container['occupiedSpace'] - item_volume)
                                break
                
                items_removed += 1
        
        # Remove items from items_list
        items_list = [item for item in items_list if item['itemId'] not in items_to_remove]
        
        # Save updated data
        with open(ITEMS_FILE, 'w') as f:
            json.dump(items_list, f, indent=2)
        
        with open(CONTAINERS_FILE, 'w') as f:
            json.dump(containers_list, f, indent=2)
        
        # Add a log entry for this action
        add_log(
            action="complete_undocking",
            details={
                "undockingContainerId": undocking_container_id,
                "timestamp": timestamp or CURRENT_DATE.isoformat(),
                "itemsRemoved": items_removed
            }
        )
        
        return jsonify({
            "success": True,
            "itemsRemoved": items_removed
        })
    
    except Exception as e:
        error_message = str(e)
        print(f"Error in complete_undocking: {error_message}")
        return jsonify({"success": False, "error": error_message}), 500

@app.route('/api/items/import', methods=['POST'])
def import_items():
    """Import items from a CSV file"""
    print(f"Import items request received: {request.files}")
    if 'file' not in request.files:
        print("No file in request.files")
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        print("Empty filename")
        return jsonify({"error": "No file selected"}), 400
    
    print(f"Processing file: {file.filename}")
    
    try:
        # Read the CSV file
        file_content = file.read()
        print(f"File size: {len(file_content)} bytes")
        stream = io.StringIO(file_content.decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        # Load existing items
        items = []
        if ITEMS_FILE.exists():
            with open(ITEMS_FILE, 'r') as f:
                items = json.load(f)
        else:
            # Initialize with empty array if file doesn't exist
            items = []
        
        # Process each row
        imported_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=1):
            try:
                # Map CSV columns to our expected format
                item_id = row.get('item_id', row.get('itemId', '')).strip()
                
                if not item_id:
                    errors.append(f"Row {row_num}: Missing item ID")
                    continue
                
                name = row.get('name', '').strip()
                width = float(row.get('width_cm', row.get('width', 0)))
                depth = float(row.get('depth_cm', row.get('depth', 0)))
                height = float(row.get('height_cm', row.get('height', 0)))
                mass = float(row.get('mass_kg', row.get('mass', 0)))
                priority = int(row.get('priority', 50))
                expiry_date = row.get('expiry_date', row.get('expiryDate', 'N/A')).strip()
                usage_limit = int(row.get('usage_limit', row.get('usageLimit', 1)))
                preferred_zone = row.get('preferred_zone', row.get('preferredZone', '')).strip()
                
                # Clean and convert data types
                item = {
                    "itemId": item_id,
                    "name": name,
                    "width": width,
                    "depth": depth,
                    "height": height,
                    "mass": mass,
                    "priority": priority,
                    "expiryDate": expiry_date,
                    "usageLimit": usage_limit,
                    "preferredZone": preferred_zone,
                    "isWaste": False,
                    "currentLocation": None
                }
                
                # Check if this item already exists (by ID)
                existing_item_index = next((i for i, existing in enumerate(items) 
                                          if existing['itemId'] == item['itemId']), None)
                
                if existing_item_index is not None:
                    # Update existing item
                    items[existing_item_index] = item
                else:
                    # Add new item
                    items.append(item)
                
                imported_count += 1
            except Exception as row_error:
                errors.append(f"Row {row_num}: {str(row_error)}")
        
        # Save updated items
        with open(ITEMS_FILE, 'w') as f:
            json.dump(items, f, indent=2)
        
        # Add a log entry
        add_log(
            action="import_items",
            details={
                "importedCount": imported_count, 
                "filename": file.filename,
                "errors": errors
            }
        )
        
        return jsonify({
            "success": True, 
            "importedCount": imported_count,
            "errors": errors
        })
    
    except Exception as e:
        print(f"Error importing items: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/api/containers/import', methods=['POST'])
def import_containers():
    """Import containers from a CSV file"""
    print(f"Import containers request received: {request.files}")
    if 'file' not in request.files:
        print("No file in request.files")
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        print("Empty filename")
        return jsonify({"error": "No file selected"}), 400
    
    print(f"Processing file: {file.filename}")
    
    try:
        # Read the CSV file
        file_content = file.read()
        print(f"File size: {len(file_content)} bytes")
        stream = io.StringIO(file_content.decode("UTF8"), newline=None)
        csv_reader = csv.DictReader(stream)
        
        # Load existing containers
        containers = []
        if CONTAINERS_FILE.exists():
            with open(CONTAINERS_FILE, 'r') as f:
                containers = json.load(f)
        else:
            # Initialize with empty array if file doesn't exist
            containers = []
        
        # Process each row
        imported_count = 0
        errors = []
        
        for row_num, row in enumerate(csv_reader, start=1):
            try:
                # Map CSV columns to our expected format
                container_id = row.get('container_id', row.get('containerId', '')).strip()
                
                if not container_id:
                    errors.append(f"Row {row_num}: Missing container ID")
                    continue
                
                zone = row.get('zone', '').strip()
                width = float(row.get('width_cm', row.get('width', 0)))
                depth = float(row.get('depth_cm', row.get('depth', 0)))
                height = float(row.get('height_cm', row.get('height', 0)))
                
                # Clean and convert data types
                container = {
                    "containerId": container_id,
                    "zone": zone,
                    "width": width,
                    "depth": depth,
                    "height": height,
                    "occupiedSpace": 0,
                    "items": []
                }
                
                # Check if this container already exists (by ID)
                existing_container_index = next((i for i, existing in enumerate(containers) 
                                              if existing['containerId'] == container['containerId']), None)
                
                if existing_container_index is not None:
                    # Preserve existing items and occupied space when updating
                    container["items"] = containers[existing_container_index].get("items", [])
                    container["occupiedSpace"] = containers[existing_container_index].get("occupiedSpace", 0)
                    
                    # Update existing container
                    containers[existing_container_index] = container
                else:
                    # Add new container
                    containers.append(container)
                
                imported_count += 1
            except Exception as row_error:
                errors.append(f"Row {row_num}: {str(row_error)}")
        
        # Save updated containers
        with open(CONTAINERS_FILE, 'w') as f:
            json.dump(containers, f, indent=2)
        
        # Add a log entry
        add_log(
            action="import_containers",
            details={
                "importedCount": imported_count, 
                "filename": file.filename,
                "errors": errors
            }
        )
        
        return jsonify({
            "success": True, 
            "importedCount": imported_count,
            "errors": errors
        })
    
    except Exception as e:
        print(f"Error importing containers: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "traceback": traceback.format_exc()}), 500

@app.route('/api/containers')
def get_containers():
    """Get all containers"""
    if CONTAINERS_FILE.exists():
        with open(CONTAINERS_FILE, 'r') as f:
            containers = json.load(f)
        return jsonify(containers)
    return jsonify([])

@app.route('/api/items')
def get_items():
    """Get all items"""
    if ITEMS_FILE.exists():
        with open(ITEMS_FILE, 'r') as f:
            items = json.load(f)
        return jsonify(items)
    return jsonify([])

@app.route('/api/logs')
def get_logs():
    """Get system logs with advanced filtering
    
    Query Parameters:
    - startDate: string (ISO format)
    - endDate: string (ISO format)
    - itemId: string (optional)
    - userId: string (optional)
    - actionType: string (optional)
      Possible values: "placement", "retrieval", "rearrangement", "disposal", etc.
    """
    # Get filter parameters from query string
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    item_id = request.args.get('itemId')
    user_id = request.args.get('userId')
    action_type = request.args.get('actionType')
    
    # Get logs from the logging service with filters
    from services.logging_service import LoggingService
    logging_service = LoggingService()
    filtered_logs = logging_service.get_logs(
        start_date=start_date,
        end_date=end_date,
        item_id=item_id,
        user_id=user_id,
        action_type=action_type
    )
    
    # Return in the standardized format
    return jsonify({"logs": filtered_logs})

@app.route('/api/logs/add', methods=['POST'])
def add_log_route():
    """Add a log entry through the API
    
    Request Body:
    {
        "actionType": "string",
        "itemId": "string" (optional),
        "userId": "string" (optional),
        "details": {
            "fromContainer": "string" (optional),
            "toContainer": "string" (optional),
            "reason": "string" (optional),
            ...other details
        }
    }
    """
    data = request.json
    action = data.get('actionType', '')
    details = data.get('details', {})
    user_id = data.get('userId', 'user')
    item_id = data.get('itemId')
    
    # Use the enhanced logging service
    from services.logging_service import LoggingService
    logging_service = LoggingService()
    log_entry = logging_service.add_log(action, details, user_id, item_id)
    
    return jsonify(log_entry)

# Route for Docker health check
@app.route('/api/health')
def health_check():
    """Simple health check endpoint"""
    return jsonify({"status": "ok", "timestamp": datetime.datetime.now().isoformat()})

# Clear data files on startup to fix issue with items appearing before CSV upload
def clear_data_files():
    """Clear data files to ensure clean state"""
    with open(ITEMS_FILE, 'w') as f:
        json.dump([], f)
    
    with open(CONTAINERS_FILE, 'w') as f:
        json.dump([], f)
    
    with open(LOGS_FILE, 'w') as f:
        json.dump([], f)
    
    add_log(action="system_startup", details={"message": "Data files cleared for clean state"})

# Call the function immediately to clear data on startup
clear_data_files()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)