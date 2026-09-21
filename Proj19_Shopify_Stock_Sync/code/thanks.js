const THANK_YOU_TAG = 'proj19-thanked';

function planThankYous(orders, allowList) {
  const allowed = new Set((allowList ?? []).map((e) => String(e).toLowerCase()));
  const send = [];
  const skip = [];
  for (const order of orders ?? []) {
    const email = typeof order?.email === 'string' ? order.email.trim() : '';
    const tags = Array.isArray(order?.tags) ? order.tags : [];
    if (!email) {
      skip.push({ orderId: order?.id, reason: 'no email address' });
    } else if (tags.includes(THANK_YOU_TAG)) {
      skip.push({ orderId: order?.id, reason: 'already thanked' });
    } else if (!allowed.has(email.toLowerCase())) {
      skip.push({ orderId: order?.id, reason: 'email is not on the allow-list' });
    } else {
      send.push({ orderId: order.id, name: order.name, email });
    }
  }
  return { send, skip };
}

// A fixed template, never model-written: nothing here can be steered by order data other than the order name.
function thankYouEmail(orderName) {
  return {
    subject: `Thanks for your order ${orderName}`,
    text: `Hi,\n\nThanks for your order ${orderName}. This is a demo store for a portfolio project, so nothing ships, but the order is confirmed.\n\nJhurald`,
  };
}

// --- exports (stripped when embedded in n8n) ---
module.exports = { THANK_YOU_TAG, planThankYous, thankYouEmail };
