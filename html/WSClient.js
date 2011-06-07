$(function () {

function log (msg) {
    var logObj = $("#log");
    var message = logObj.html();
    logObj.html(message + msg + "<br>");
}

$("#connectBtn").click(function () {
    var host = $("#host").val();
    var port = $("#port").val();
    var resource = $("#resource").val();
    var subprotocol = $('#subprotocol').val();

    if (subprotocol) ws = new WebSocket("ws://" + host + ":" + port + resource, subprotocol);
    else ws = new WebSocket("ws://" + host + ":" + port + resource);
    ws.onopen = function () { 
        log("WebSocket open");
        $("#connectBtn").hide();
        $("#disconnectBtn").show();
    };
    ws.onmessage = function (e) {
        log('received "' + e.data + '"');
    };
    ws.onclose = function () {
        log("WebSocket close");
        $("#disconnectBtn").hide();
        $("#connectBtn").show();
    };
    ws.onerror = function (e) {
        log("WebSocket error: " + e.name);
    };
});

$("#disconnectBtn").click(function () {
    ws.close();
});

$("#sendBtn").click(function () {
    var msg = $("#msg").val();
    if (msg == "") return false;
    if (ws.send(msg)) $("#msg").val("");
});

})
