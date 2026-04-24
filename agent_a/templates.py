"""
Response templates used by Agent A (rule-based DineBot).

Each template is either a single string or a dict keyed by sub-intent.
Agent A selects the appropriate template based on the classified intent
and optionally injects retrieved knowledge base context.
"""

from __future__ import annotations

GREETING_TEMPLATES: list[str] = [
    "Hello! I am DineBot, your friendly delivery assistant. How can I help you today?",
    "Hi there! DineBot at your service. Ask me about our menu, delivery status, or table service.",
    "Good day! DineBot reporting for duty. I can answer menu questions and deliver food to your table.",
]

SAFETY_TEMPLATES: dict[str, str] = {
    "distance": (
        "For your safety, I always keep at least 0.5 meters from people and "
        "trigger an emergency stop if anyone comes within 0.3 meters."
    ),
    "stop": (
        "Understood. If you say STOP or EMERGENCY, I halt immediately and wait "
        "for a RESUME command from a staff member."
    ),
    "speed": (
        "My maximum speed is 0.5 meters per second. I slow down further when "
        "humans are nearby to avoid any risk."
    ),
    "obstacle": (
        "When I detect an obstacle, I stop within 0.3 meters, announce the "
        "obstacle, wait up to 30 seconds, and try an alternate mapped route."
    ),
    "emergency": (
        "In an emergency I stop in place, flash my warning LEDs, and alert "
        "the staff console immediately."
    ),
    "danger": (
        "Safety always comes first. I refuse any action that could endanger a "
        "human and escalate unclear situations to staff."
    ),
    "safe": (
        "I follow strict safety rules: 0.5 m minimum human distance, 0.5 m/s "
        "max speed, and flat indoor surfaces only."
    ),
    "halt": (
        "On a HALT command I stop immediately in place and wait for RESUME."
    ),
}

DELIVERY_TEMPLATES: dict[str, str] = {
    "confirm": (
        "Before I depart, I confirm the table number with the kitchen staff "
        "and repeat it aloud. I only leave after staff taps the confirmation "
        "button."
    ),
    "arrive": (
        "When I arrive I announce: 'DineBot has arrived at your table with "
        "your order.' Please collect your items within 30 seconds."
    ),
    "wait": (
        "Average preparation time is 15 to 20 minutes. Travel from the dock "
        "to your table is between 20 and 75 seconds depending on the zone."
    ),
    "return": (
        "Once your tray is empty I announce 'Delivery complete, returning to "
        "dock' and take my designated return path back."
    ),
    "fail": (
        "If a delivery fails (wrong table, blocked path, or spill) I hold "
        "position, do not unload, and alert a human staff member."
    ),
    "default": (
        "I deliver food and beverages from the kitchen to tables 1-10 and "
        "16-20. Tables 11-15 are on the outdoor terrace and are handled by "
        "human staff."
    ),
}

MENU_TEMPLATES: dict[str, str] = {
    "appetizers": (
        "Our appetizers today: Spring Rolls (vegan), Garlic Bread, Caesar "
        "Salad, and Tomato Soup. Ask our staff for allergen details."
    ),
    "mains": (
        "Main courses include Grilled Salmon, Ribeye Steak, Margherita Pizza, "
        "Pasta Carbonara, and a Veggie Burger with a vegan bun option."
    ),
    "desserts": (
        "For dessert we have Chocolate Lava Cake, Cheesecake, Ice Cream Sundae, "
        "and classic Tiramisu."
    ),
    "beverages": (
        "We serve still and sparkling water, fresh orange juice, Coca-Cola, "
        "lemonade, coffee, tea, and a small wine selection (adults only)."
    ),
    "default": (
        "Our menu is split into appetizers, mains, desserts, and beverages. "
        "Which section would you like to hear about?"
    ),
}

STATUS_TEMPLATES: dict[str, str] = {
    "IDLE": "I am currently IDLE at the docking station, ready for a task.",
    "LOADING": "I am at the kitchen counter LOADING your order.",
    "DELIVERING": "I am DELIVERING an order right now. Please keep the path clear.",
    "WAITING": "I have arrived and am WAITING for the customer to collect items.",
    "RETURNING": "I am RETURNING to the docking station after a delivery.",
    "EMERGENCY": "EMERGENCY! I have stopped and alerted the staff console.",
    "LOW_BATTERY": "My battery is below 20%. I am heading back to the dock to recharge.",
    "default": (
        "Status: operational. You can ask me about current battery, state, "
        "or estimated wait time."
    ),
}

EMERGENCY_TEMPLATES: dict[str, str] = {
    "fire": (
        "Fire alarm response: I stop immediately, announce evacuation, flash "
        "red LEDs, and broadcast an alert to all staff consoles."
    ),
    "spill": (
        "If I detect a spill I stop, announce the spill location, flash "
        "yellow LEDs, and wait for a staff member to clean the area."
    ),
    "obstacle": (
        "Obstacle protocol: stop within 0.3 m, announce the obstacle, wait "
        "up to 30 s, then try an alternate mapped route."
    ),
    "power": (
        "On power failure I execute a safe stop, lower the tray, and enter "
        "low-power sleep mode until staff restores power."
    ),
    "collision": (
        "If a human enters the 0.3 m emergency zone I trigger an emergency "
        "stop and politely ask the person to step aside."
    ),
    "evacuate": (
        "During an evacuation I hold position in a safe corridor and keep "
        "the announcement speaker active for staff coordination."
    ),
    "help": (
        "I am calling a staff member to assist you right now. Please stay "
        "where you are."
    ),
    "alarm": (
        "Alarm acknowledged. I have halted movement and notified staff."
    ),
    "default": (
        "I follow strict emergency protocols: stop, announce, alert staff, "
        "and wait for a human decision."
    ),
}

FALLBACK_TEMPLATE: str = (
    "That request is outside my scope as a food delivery robot. "
    "Please ask a human staff member; they will be happy to help you."
)
