// Utils
function utilToHex(n, pad) {
    pad = (typeof pad !== 'undefined') ? pad : 1;
    var s = Number(n).toString(16);
    while (s.length < pad) {
        s = '0' + s;
    }
    return s;
}

// Classes
/**
 * Register
 */
function Register(name, type, id) {
    // Helpers
    this._update_int = function () {
        var value = e.reg_read_int(this.id);
        switch (this.type) {
            case 'i8':  this.nodeValue.innerHTML = utilToHex(value, 2);
            case 'i16': this.nodeValue.innerHTML = utilToHex(value, 4);
            case 'i32': this.nodeValue.innerHTML = utilToHex(value, 8);
        }
    }
    this._update_float = function () {
        var value = e.reg_read(); // TODO
    }
    this._update_vector = function () {
        var value = e.reg_read(); // TODO
    }

    // Methods
    this.update = function () {
        switch (this.type) {
            case 'i8':
            case 'i16':
            case 'i32':
                this._update_int();
            case 'f32':
                this._update_float();
            case 'v128':
                this._update_vector();
        }
    }

    // Constructor
    this.name = name;
    this.type = type;
    this.id = id;

    this.node = document.createElement("div");
    this.nodeName = document.createElement("span");
    this.nodeValue = document.createElement("span");
    this.nodeName.innerHTML = name
    this.node.appendChild(this.nodeName);
    this.node.appendChild(this.nodeValue);

    this.update();
}

/**
 * Instruction
 */
function Instruction() {
    this.bytes = [];
    this.asm = "";

    this.nodeAddr = document.createElement("div");
    this.nodeHex = document.createElement("div");
    this.nodeAsm = document.createElement("div");

    // Methods
    this.setHex = function (hex) {

    }
    this.setAsm = function (asm) {

    }
    this.length = function () {
        return this.bytes.length;
    }
}

// Panes
var paneAssembler = {
    address: 0x10000,
};

var paneRegisters = {
    registers: [],

    add: function (reg) {
        var regs = document.getElementById('registers');
        regs.appendChild(reg.node);
    },
    update: function () {
        for (var i = 0; i < register.length; i++) {
            registers[i].update();
        }
    }
};


$(document).ready(function () {
    Split(['#pane-l', '#pane-r'], {
        gutterSize: 8,
        sizes: [65, 35],
        cursor: 'col-resize'
    });
    Split(['#pane-lt', '#pane-lb'], {
        direction: 'vertical',
        sizes: [65, 35],
        gutterSize: 8,
        cursor: 'row-resize'
    });
    Split(['#pane-rt', '#pane-rb'], {
        direction: 'vertical',
        sizes: [65, 35],
        gutterSize: 8,
        cursor: 'row-resize'
    });
});
