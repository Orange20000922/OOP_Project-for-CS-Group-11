(function initKnowledgeGraph(global) {
  function createPalette(groups) {
    const colors = [
      "#a43c2f",
      "#1d6f68",
      "#b57f26",
      "#5f4b8b",
      "#2f7d32",
      "#7a3e65",
      "#ca5a2c",
      "#3567a5",
    ];

    const map = {};
    groups.forEach(function assignColor(group, index) {
      map[group] = colors[index % colors.length];
    });
    return map;
  }

  function buildElements(graph) {
    const nodes = Array.isArray(graph && graph.nodes) ? graph.nodes : [];
    const links = Array.isArray(graph && graph.links) ? graph.links : [];
    const degrees = {};

    links.forEach(function countDegree(link) {
      degrees[link.source] = (degrees[link.source] || 0) + 1;
      degrees[link.target] = (degrees[link.target] || 0) + 1;
    });

    const palette = createPalette(
      Array.from(
        new Set(
          nodes.map(function collectGroup(node) {
            return node.group || node.note_id || "default";
          })
        )
      )
    );

    return {
      palette: palette,
      elements: {
        nodes: nodes.map(function toNode(node) {
          var group = node.group || node.note_id || "default";
          return {
            data: {
              id: node.id,
              label: node.label,
              noteId: node.note_id,
              noteTitle: node.note_title || "",
              topicId: node.topic_id || "",
              chunkIndex: node.chunk_index,
              preview: node.content_preview || "",
              group: group,
              degree: degrees[node.id] || 0,
              color: palette[group],
            },
          };
        }),
        edges: links.map(function toEdge(link, index) {
          return {
            data: {
              id: "edge-" + index,
              source: link.source,
              target: link.target,
              weight: Number(link.value || 0),
            },
          };
        }),
      },
    };
  }

  function create(container, options) {
    if (!container || !global.cytoscape) {
      return {
        render: function noop() {},
        resize: function noopResize() {},
        destroy: function noopDestroy() {},
      };
    }

    var cy = global.cytoscape({
      container: container,
      elements: [],
      layout: { name: "preset" },
      style: [
        {
          selector: "node",
          style: {
            width: "mapData(degree, 0, 8, 28, 54)",
            height: "mapData(degree, 0, 8, 28, 54)",
            label: "data(label)",
            "background-color": "data(color)",
            "border-width": 2,
            "border-color": "#fff8ee",
            color: "#281611",
            "font-size": 11,
            "font-weight": 600,
            "text-wrap": "wrap",
            "text-max-width": 92,
            "text-valign": "bottom",
            "text-margin-y": 9,
            "overlay-opacity": 0,
            "shadow-blur": 18,
            "shadow-color": "rgba(0,0,0,0.16)",
            "shadow-offset-y": 10,
            "shadow-opacity": 0.16,
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(weight, 0, 1, 1, 6)",
            "line-color": "rgba(124, 86, 67, 0.32)",
            "curve-style": "bezier",
            "target-arrow-shape": "none",
            opacity: 0.82,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 4,
            "border-color": "#f4c27f",
            "shadow-color": "rgba(244, 194, 127, 0.56)",
            "shadow-opacity": 0.42,
            "shadow-blur": 22,
          },
        },
        {
          selector: ".faded",
          style: {
            opacity: 0.18,
          },
        },
      ],
    });

    cy.on("tap", "node", function onTap(event) {
      var node = event.target;
      cy.elements().addClass("faded");
      node.removeClass("faded");
      node.closedNeighborhood().removeClass("faded");
      if (options && typeof options.onSelect === "function") {
        options.onSelect({
          id: node.id(),
          label: node.data("label"),
          note_id: node.data("noteId"),
          note_title: node.data("noteTitle"),
          topic_id: node.data("topicId") || null,
          chunk_index: node.data("chunkIndex"),
          content_preview: node.data("preview"),
        });
      }
    });

    cy.on("tap", function onBlank(event) {
      if (event.target !== cy) {
        return;
      }
      cy.elements().removeClass("faded");
    });

    function render(graph) {
      var built = buildElements(graph || {});
      cy.elements().remove();
      cy.add(built.elements);

      if (!built.elements.nodes.length) {
        cy.resize();
        cy.fit(undefined, 32);
        return;
      }

      cy.layout({
        name: built.elements.nodes.length > 1 ? "cose" : "grid",
        fit: true,
        animate: true,
        animationDuration: 320,
        padding: 28,
        nodeRepulsion: 9800,
        idealEdgeLength: 140,
        edgeElasticity: 120,
        gravity: 0.16,
        nestingFactor: 0.9,
        numIter: 500,
      }).run();
    }

    return {
      render: render,
      resize: function resize() {
        cy.resize();
        cy.fit(undefined, 24);
      },
      destroy: function destroy() {
        cy.destroy();
      },
    };
  }

  global.knowledgeGraph = {
    create: create,
  };
})(window);
