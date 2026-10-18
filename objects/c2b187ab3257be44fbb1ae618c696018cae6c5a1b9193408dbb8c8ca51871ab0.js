/* Independent-AdBlock v2 — Shadowrocket http-response, JavaScriptCore.
 * Original, local-only filter. Endpoint/schema references: SOURCES.md.
 * No network, storage, request changes, login/VIP changes or content logging.
 * Unknown endpoints/schemas and errors pass through the original response.
 */
(function () {
  "use strict";
  var version = "v2";
  var zhihu = /^https?:\/\/(?:(?:api|web-render)\.zhihu\.com\/topstory\/recommend|api\.zhihu\.com\/(?:next-render|questions\/\d+\/feeds?|moments_v3))(?:[/?]|$)/;
  var weibo = /^https?:\/\/m?api\.weibo\.(?:cn|com)\/2\/(?:statuses\/(?:friends\/timeline|(?:unread_)?friends_timeline|unread_hot_timeline|container_timeline(?:_hot|_unread|_topic|_topicpage)?|container_detail(?:_comment|_mix|_forward)?|repost_timeline|extend)|groups\/timeline|cardlist|searchall|page|flowpage|search\/(?:finder|container_timeline|container_discover)|comments\/(?:mix_comments|build_comments))(?:[/?]|$)/;

  function object(x) { return x !== null && typeof x === "object" && !Array.isArray(x); }
  function flag(x) { return x === 1 || x === "1" || x === true; }
  function adMarker(x, service, depth) {
    if (!object(x) || depth > 2) return false;
    if (service === "zhihu") {
      if (x.type === "feed_advert" || x.type === "market_card") return true;
      if (x.extra && x.extra.type === "SvipActivity") return true;
      // A null/false ad field also occurs on ordinary items; keep those items.
      if (object(x.ad) || flag(x.ad)) return true;
    } else {
      if (flag(x.is_ad) || flag(x.ad_state)) return true;
      if (typeof x.mblogtypename === "string" && /广告|热推/.test(x.mblogtypename)) return true;
      if (x.promotion && x.promotion.type === "ad") return true;
      if (x.ads_material_info && flag(x.ads_material_info.is_ads)) return true;
      if (x.content_auth_info && typeof x.content_auth_info.content_auth_title === "string" &&
          x.content_auth_info.content_auth_title.indexOf("广告") !== -1) return true;
    }
    // Inspect feed wrappers, not a post's text, author, or quoted/reposted post.
    var wrappers = service === "zhihu" ? ["data", "target"] : ["data", "mblog", "status"];
    return wrappers.some(function (key) { return adMarker(x[key], service, depth + 1); });
  }

  // JSON.parse/JSON.stringify otherwise silently round Weibo's 64-bit IDs.
  // Mask only long integer tokens outside JSON strings, then restore verbatim.
  function decode(body) {
    var prefix = "__sr_integer_";
    while (body.indexOf(prefix) !== -1) prefix += "_";
    var integers = [], output = [], quoted = false, escaped = false;
    for (var i = 0; i < body.length;) {
      var c = body[i];
      if (quoted) {
        output.push(c); i++;
        if (escaped) escaped = false;
        else if (c === "\\") escaped = true;
        else if (c === '"') quoted = false;
      } else if (c === '"') {
        quoted = true; output.push(c); i++;
      } else if (c === "-" || /[0-9]/.test(c)) {
        var start = i++;
        while (i < body.length && /[0-9eE+.\-]/.test(body[i])) i++;
        var token = body.slice(start, i);
        if (/^-?[1-9]\d{15,}$/.test(token)) {
          output.push(JSON.stringify(prefix + integers.length)); integers.push(token);
        } else output.push(token);
      } else { output.push(c); i++; }
    }
    return {
      value: JSON.parse(output.join("")),
      encode: function (value) {
        var result = JSON.stringify(value);
        integers.forEach(function (token, index) {
          result = result.split(JSON.stringify(prefix + index)).join(token);
        });
        return result;
      }
    };
  }

  try {
    var url = $request.url || "";
    var service = zhihu.test(url) ? "zhihu" : weibo.test(url) ? "weibo" : null;
    var body = $response.body;
    if (!service || typeof body !== "string" || !body || body.length > 4000000) {
      $done({}); return;
    }
    var decoded = decode(body), response = decoded.value;
    if (!object(response) || response.error ||
        (response.code !== undefined && response.code !== 0 && response.code !== "0" && response.code !== 200)) {
      $done({}); return;
    }
    var collections = service === "zhihu" ? ["data", "items", "feeds", "feed"] :
      ["data", "items", "cards", "card_group", "statuses", "reposts", "hot_reposts", "comments"];
    var removed = 0, visited = 0;
    function walk(node, depth) {
      if (node === null || typeof node !== "object") return;
      if (++visited > 20000 || depth > 24) throw new Error("response exceeds traversal limit");
      Object.keys(node).forEach(function (key) {
        var value = node[key];
        if (Array.isArray(value) && collections.indexOf(key) !== -1) {
          value = value.filter(function (entry) {
            if (adMarker(entry, service, 0)) { removed++; return false; }
            return true;
          });
          node[key] = value;
        }
        if (value !== null && typeof value === "object") walk(value, depth + 1);
      });
    }
    walk(response, 0);
    // No reserialization at all when nothing was removed.
    if (!removed) { $done({}); return; }
    var result = decoded.encode(response);
    console.log("Independent-AdBlock " + version + " " + service + ": removed " + removed);
    $done({body: result});
  } catch (error) {
    console.log("Independent-AdBlock " + version + ": response unchanged (unrecognized data)");
    $done({});
  }
})();
