const React = require("react");

function Link({ href, children, ...props }) {
  return React.createElement("a", { href, ...props }, children);
}

module.exports = Link;
module.exports.default = Link;
