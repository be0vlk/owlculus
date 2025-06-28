chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === "captureHTML") {
    capturePageHTML().then((result) => {
      sendResponse(result);
    });
    return true;
  }
});

async function capturePageHTML() {
  try {
    const doctype = document.doctype
      ? `<!DOCTYPE ${document.doctype.name}>`
      : "";

    const htmlElement = document.documentElement.cloneNode(true);

    removeScripts(htmlElement);
    removeSensitiveData(htmlElement);

    const pageMetadata = {
      title: document.title || "Untitled Page",
      url: window.location.href,
      capturedAt: new Date().toISOString(),
      viewport: {
        width: window.innerWidth,
        height: window.innerHeight,
      },
    };

    const metaTag = document.createElement("meta");
    metaTag.name = "owlculus-metadata";
    metaTag.content = JSON.stringify(pageMetadata);

    const head = htmlElement.querySelector("head");
    if (head) {
      head.appendChild(metaTag);
    }

    const fullHTML = doctype + htmlElement.outerHTML;

    return {
      success: true,
      html: fullHTML,
      metadata: pageMetadata,
    };
  } catch (error) {
    console.error("Error capturing HTML:", error);
    return {
      success: false,
      error: error.message,
    };
  }
}

function removeScripts(element) {
  const scripts = element.querySelectorAll("script");
  scripts.forEach((script) => script.remove());

  const onEventAttrs = Array.from(element.querySelectorAll("*")).filter(
    (el) => {
      return Array.from(el.attributes).some((attr) =>
        attr.name.startsWith("on"),
      );
    },
  );

  onEventAttrs.forEach((el) => {
    Array.from(el.attributes)
      .filter((attr) => attr.name.startsWith("on"))
      .forEach((attr) => el.removeAttribute(attr.name));
  });
}

function removeSensitiveData(element) {
  const sensitiveInputs = element.querySelectorAll('input[type="password"]');
  sensitiveInputs.forEach((input) => {
    input.value = "";
    input.setAttribute("value", "");
  });

  const csrfTokens = element.querySelectorAll(
    '[name*="csrf"], [name*="token"], [data-csrf]',
  );
  csrfTokens.forEach((el) => {
    if (el.value) el.value = "[REDACTED]";
    if (el.hasAttribute("data-csrf"))
      el.setAttribute("data-csrf", "[REDACTED]");
  });
}
