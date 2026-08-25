/*
 * Able2Answer Live Bridge
 *
 * Runs inside a Max for Live device in Ableton Live. Its only job is to read
 * the current Live Set and hand a structured snapshot to Abel. It deliberately
 * contains no intelligence: no analysis, no thresholds, no advice. Everything
 * it emits is a value it actually read.
 *
 * v0.1 is READ ONLY. It calls no setter and no LOM function that mutates the
 * Live Set. The producer remains the authority over their session.
 *
 * Two sources, because one is not enough:
 *
 *   LiveAPI    — the Live Object Model: tempo, tracks, devices, selection.
 *   adstatus   — Max's audio driver status.
 *
 * The second is needed because the Live Object Model does not expose the audio
 * interface sample rate or buffer size at all. Max for Live runs inside Live's
 * own audio engine, so `adstatus sr` and `adstatus iovs` report the values
 * Live is actually running at. Those arrive on inlets 1 and 2 (see README.md);
 * until they do, they stay null and Abel reports them as unknown rather than
 * assuming 44100.
 */

autowatch = 1;
inlets = 3;   // 0: bang to capture   1: sample rate   2: buffer size
outlets = 1;  // the snapshot, as JSON

var BRIDGE_VERSION = "0.1.0";

// Populated by adstatus, not by the Live Object Model. Null until reported.
var sampleRate = null;
var bufferSize = null;

function msg_float(value) {
    if (inlet === 1) {
        sampleRate = value;
    } else if (inlet === 2) {
        bufferSize = value;
    }
}

/* Read one property, returning null rather than throwing when Live does not
 * have it. Properties vary across Live versions and track types, and a missing
 * reading must stay missing all the way to the producer. */
function read(api, property) {
    try {
        var value = api.get(property);
        if (value === undefined || value === null) return null;
        // LiveAPI returns single values wrapped in a one-element array.
        if (value instanceof Array) {
            if (value.length === 0) return null;
            return value.length === 1 ? value[0] : value;
        }
        return value;
    } catch (e) {
        return null;
    }
}

function trackTypeOf(path) {
    // The LOM path itself is the reliable discriminator; a track's name is not.
    if (path.indexOf("return_tracks") !== -1) return "return";
    if (path.indexOf("master_track") !== -1) return "main";
    var api = new LiveAPI(path);
    // has_midi_input distinguishes a MIDI track from an audio track.
    return read(api, "has_midi_input") ? "midi" : "audio";
}

function readDevices(trackPath) {
    var devices = [];
    var chain = new LiveAPI(trackPath + " devices");
    var count = chain.getcount("devices");
    for (var i = 0; i < count; i++) {
        var device = new LiveAPI(trackPath + " devices " + i);
        var name = read(device, "name");
        var className = read(device, "class_name");
        if (name === null && className === null) continue;
        devices.push({
            name: name === null ? String(className) : String(name),
            class_name: className === null ? String(name) : String(className),
            // Live reports a bypassed device as is_active 0.
            is_active: read(device, "is_active")
        });
    }
    return devices;
}

function readTracks() {
    var tracks = [];
    var liveSet = new LiveAPI("live_set");
    var groups = ["tracks", "return_tracks"];
    var index = 0;

    for (var g = 0; g < groups.length; g++) {
        var count = liveSet.getcount(groups[g]);
        for (var i = 0; i < count; i++) {
            var path = "live_set " + groups[g] + " " + i;
            var api = new LiveAPI(path);
            tracks.push({
                index: index++,
                name: String(read(api, "name")),
                type: trackTypeOf(path),
                is_frozen: read(api, "is_frozen"),
                is_muted: read(api, "mute"),
                is_soloed: read(api, "solo"),
                devices: readDevices(path)
            });
        }
    }
    return tracks;
}

function selectedTrackIndex(tracks) {
    var view = new LiveAPI("live_set view selected_track");
    var name = read(view, "name");
    if (name === null) return null;
    // The view reports the selected track by object, not by index, so it is
    // matched back against the tracks actually sent. An unmatched selection is
    // reported as none rather than as a guessed index.
    var id = view.id;
    for (var i = 0; i < tracks.length; i++) {
        var candidate = new LiveAPI("live_set tracks " + i);
        if (candidate.id === id) return tracks[i].index;
    }
    return null;
}

/* Capture one snapshot and send it out. Triggered by a bang on inlet 0. */
function bang() {
    var liveSet = new LiveAPI("live_set");
    var app = new LiveAPI("live_app");
    var tracks = readTracks();

    var snapshot = {
        bridge_version: BRIDGE_VERSION,
        captured_at: null,          // stamped by Abel on receipt; Max has no ISO clock
        live_version: null,
        set: {
            name: null,             // the LOM does not expose the Set's file name
            tempo: read(liveSet, "tempo"),
            signature_numerator: read(liveSet, "signature_numerator"),
            signature_denominator: read(liveSet, "signature_denominator"),
            is_playing: read(liveSet, "is_playing")
        },
        audio: {
            sample_rate: sampleRate,
            buffer_size: bufferSize
        },
        tracks: tracks,
        selected_track_index: selectedTrackIndex(tracks)
    };

    try {
        snapshot.live_version = String(app.call("get_version_string"));
    } catch (e) {
        snapshot.live_version = null;
    }

    outlet(0, JSON.stringify(snapshot));
}
