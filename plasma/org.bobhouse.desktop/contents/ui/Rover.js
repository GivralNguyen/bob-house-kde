.pragma library

// ACT group numbers and command meanings match the desktop rover.py decoder.
var aliases = {
    greeting: "1", idle: "2", look_left: "3", gesture: "4", acknowledge: "5",
    walk: "6", thinking: "7", nod: "8", roll: "9", laugh: "10", working: "11",
    ready: "12", look_back: "13", mail: "14", look_right: "15", success: "16",
    smile: "17", error: "18", surprised: "19", play: "20", writing: "21",
    cancel: "22", computer: "23", pant: "24", ask: "25", stretch: "26",
    fetch: "31", clicked: "32"
};

function create(timeline) {
    return { timeline: timeline, pose: 201, commands: [], position: 0,
             deadline: 0, started: 0, running: false, nextIdle: 0 };
}

function play(actor, name, now) {
    var animations = actor.timeline.animations || {};
    var variants = animations[aliases[name]] || animations[aliases.clicked] || [];
    actor.commands = variants.length ? variants[Math.floor(Math.random() * variants.length)] : [];
    actor.position = 0;
    actor.started = now;
    actor.deadline = now;
    actor.nextIdle = now + 14000 + Math.random() * 10000;
    actor.running = actor.commands.length > 0;
    actor.pose = 201;
}

function frame(actor, now, animate) {
    if (!animate) {
        actor.running = false;
        actor.nextIdle = now + 14000;
        actor.pose = 201;
        return 201;
    }
    if (!actor.running && now >= actor.nextIdle) play(actor, "idle", now);
    var steps = 0;
    while (actor.running && now >= actor.deadline) {
        if (actor.position >= actor.commands.length || ++steps > 1000 || now - actor.started > 90000) {
            actor.running = false;
            actor.pose = 201;
            actor.nextIdle = now + 10000 + Math.random() * 8000;
            break;
        }
        var command = actor.commands[actor.position++];
        if (command[0] === 0) {
            actor.pose = command[1];
            actor.deadline += command[2];
        } else if (command[0] === 1 && Math.floor(Math.random() * 32768) < command[2]) {
            actor.position = command[1];
        }
        // Sound cues are intentionally silent in the desktop wallpaper.
    }
    return actor.pose;
}
