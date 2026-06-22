import { useEffect, useMemo, useRef, useState } from 'react'
import cytoscape from 'cytoscape'
import type { ElementDefinition } from 'cytoscape'
import { Card, Chip, DataValue, Eyebrow, Panel } from '../../components/ui'
import { mockGraph } from '../../mocks'
import type { GraphEdge, GraphNode } from '../../types'
import styles from './GraphView.module.css'

interface NodeRelation {
  edge: GraphEdge
  otherNode: GraphNode
  direction: 'outgoing' | 'incoming'
}

const graphElements: ElementDefinition[] = [
  ...mockGraph.nodes.map((node) => ({
    data: {
      id: node.id,
      label: node.label,
    },
  })),
  ...mockGraph.edges.map((edge) => ({
    data: {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.relationType,
    },
  })),
]

const cytoscapeStylesheet: NonNullable<cytoscape.CytoscapeOptions['style']> = [
  {
    selector: 'node',
    style: {
      // --color-accent: #6366f1; Cytoscape canvas styles cannot read CSS variables.
      'background-color': '#6366f1',
      // --color-on-accent: #ffffff.
      color: '#ffffff',
      label: 'data(label)',
      width: 58,
      height: 58,
      'border-width': 2,
      // --color-accent-border: #c7d2fe.
      'border-color': '#c7d2fe',
      'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      'font-size': 10,
      'font-weight': 'bold',
      'text-max-width': '90px',
      'text-wrap': 'wrap',
      'text-valign': 'center',
      'text-halign': 'center',
      'text-outline-width': 1,
      // --color-accent-active: #4338ca.
      'text-outline-color': '#4338ca',
      'overlay-opacity': 0,
    },
  },
  {
    selector: 'edge',
    style: {
      label: 'data(label)',
      width: 2,
      // --color-border-strong: #cbd5e1.
      'line-color': '#cbd5e1',
      'target-arrow-shape': 'triangle',
      'target-arrow-color': '#cbd5e1',
      'curve-style': 'bezier',
      // --color-text-muted: #64748b.
      color: '#64748b',
      'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      'font-size': 9,
      'font-weight': 'bold',
      'text-background-color': '#ffffff', // --color-surface: #ffffff.
      'text-background-opacity': 0.9,
      'text-background-padding': '3px',
      'text-background-shape': 'roundrectangle',
      'text-rotation': 'autorotate',
      'overlay-opacity': 0,
    },
  },
  {
    selector: 'node:selected',
    style: {
      // --color-accent-active: #4338ca.
      'background-color': '#4338ca',
      'border-width': 5,
      // --color-accent-softer: #e0e7ff.
      'border-color': '#e0e7ff',
    },
  },
  {
    selector: '.searchMatch',
    style: {
      // --color-accent-active: #4338ca.
      'background-color': '#4338ca',
      'border-width': 5,
      // --color-warning-soft: #fef3c7.
      'border-color': '#fef3c7',
    },
  },
  {
    selector: '.searchDimmed',
    style: {
      opacity: 0.22,
    },
  },
]

function findGraphNode(nodeId: string) {
  return mockGraph.nodes.find((node) => node.id === nodeId) ?? null
}

function getNodeRelations(nodeId: string): NodeRelation[] {
  return mockGraph.edges.reduce<NodeRelation[]>((relations, edge) => {
    if (edge.source === nodeId) {
      const otherNode = findGraphNode(edge.target)

      if (otherNode) {
        relations.push({ edge, otherNode, direction: 'outgoing' })
      }
    }

    if (edge.target === nodeId) {
      const otherNode = findGraphNode(edge.source)

      if (otherNode) {
        relations.push({ edge, otherNode, direction: 'incoming' })
      }
    }

    return relations
  }, [])
}

export function GraphView() {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null)
  const [searchTerm, setSearchTerm] = useState('')

  const selectedRelations = useMemo(
    () => (selectedNode ? getNodeRelations(selectedNode.id) : []),
    [selectedNode],
  )

  useEffect(() => {
    if (!containerRef.current) {
      return
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements: graphElements,
      style: cytoscapeStylesheet,
      layout: {
        name: 'cose',
        animate: false,
        fit: true,
        padding: 48,
        nodeRepulsion: 8000,
        idealEdgeLength: 110,
      },
      minZoom: 0.55,
      maxZoom: 2.2,
      wheelSensitivity: 0.15,
    })

    cyRef.current = cy

    cy.on('tap', 'node', (event) => {
      const nodeId = event.target.id()
      setSelectedNode(findGraphNode(nodeId))
    })

    cy.on('tap', (event) => {
      if (event.target === cy) {
        setSelectedNode(null)
      }
    })

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [])

  useEffect(() => {
    const cy = cyRef.current

    if (!cy) {
      return
    }

    const normalizedSearch = searchTerm.trim().toLocaleLowerCase()
    const nodes = cy.nodes()
    const edges = cy.edges()

    nodes.removeClass('searchMatch searchDimmed')
    edges.removeClass('searchDimmed')

    if (!normalizedSearch) {
      return
    }

    const matchingNodes = nodes.filter((node) => {
      const label = String(node.data('label') ?? '').toLocaleLowerCase()
      return label.includes(normalizedSearch)
    })

    nodes.not(matchingNodes).addClass('searchDimmed')
    edges.addClass('searchDimmed')
    matchingNodes.addClass('searchMatch')
    matchingNodes.connectedEdges().removeClass('searchDimmed')
  }, [searchTerm])

  return (
    <section className={styles.graphView}>
      <header className={styles.header}>
        <div className={styles.heading}>
          <Eyebrow>Knowledge Graph</Eyebrow>
          <h1 className={styles.title}>图谱探索</h1>
          <p className={styles.subtitle}>
            从 mock 图谱中探索实体与关系，后续会接入真实 Neo4j 查询与邻域扩展。
          </p>
        </div>

        <Card className={styles.searchCard} padding="md">
          <label className={styles.searchLabel}>
            <span className={styles.searchCaption}>实体搜索</span>
            <input
              className={styles.searchInput}
              type="search"
              value={searchTerm}
              placeholder="搜索实体…"
              onChange={(event) => setSearchTerm(event.target.value)}
            />
          </label>
          <span className={styles.searchHint}>输入名称会高亮匹配节点，并弱化其他图谱元素。</span>
        </Card>
      </header>

      <div className={styles.workspace}>
        <div className={styles.canvasShell} aria-label="知识图谱画布">
          <div ref={containerRef} className={styles.canvas} />
          <div className={styles.canvasNote}>拖拽移动画布，滚轮缩放，点击节点查看详情。</div>
        </div>

        <Panel className={styles.detailPanel} eyebrow="Entity Detail" title="实体详情">
          {selectedNode ? (
            <div className={styles.detailBody}>
              <div className={styles.entityHeader}>
                <div className={styles.entityTitleRow}>
                  <h2 className={styles.entityTitle}>{selectedNode.label}</h2>
                  <Chip tone="accent">{selectedNode.entityType}</Chip>
                </div>
                <DataValue label="entity id">{selectedNode.id}</DataValue>
              </div>

              <section className={styles.detailBody} aria-label="实体关系">
                <h3 className={styles.sectionTitle}>关联关系</h3>
                {selectedRelations.length > 0 ? (
                  <ul className={styles.relationList}>
                    {selectedRelations.map(({ edge, otherNode, direction }) => (
                      <li key={edge.id} className={styles.relationItem}>
                        <div className={styles.relationTopline}>
                          <span className={styles.relationType}>{edge.relationType}</span>
                          <span className={styles.relationDirection}>
                            {direction === 'outgoing' ? 'out' : 'in'}
                          </span>
                        </div>
                        <span className={styles.relationTarget}>{otherNode.label}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className={styles.noRelations}>这个实体当前没有 mock 关系。</p>
                )}
              </section>
            </div>
          ) : (
            <div className={styles.emptyState}>
              <h2 className={styles.emptyTitle}>点击图中节点查看实体详情</h2>
              <p className={styles.emptyCopy}>这里会显示实体类型、ID，以及它与其他实体之间的关系。</p>
            </div>
          )}
        </Panel>
      </div>
    </section>
  )
}
