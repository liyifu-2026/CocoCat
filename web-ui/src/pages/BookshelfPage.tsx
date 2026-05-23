import { useParams } from "react-router-dom"
import { useCallback, useState } from "react"
import Namecard from "@/components/Namecard"
import VizEngine from "@/components/viz/VizEngine"
import Bookshelf from "@/components/bookshelf/Bookshelf"
import DocRenderer from "@/components/bookshelf/DocRenderer"
import RawZone from "@/components/bookshelf/RawZone"

export default function BookshelfPage() {
  const { kbName } = useParams()
  const [selectedKb, setSelectedKb] = useState<string | null>(kbName || null)

  // Sync with URL param changes
  const currentKbName = kbName || selectedKb

  const handleSelect = useCallback((name: string) => {
    setSelectedKb(name)
  }, [])

  return (
    <>
      <Namecard />
      <VizEngine />
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        <DocRenderer kbName={currentKbName} />
        <Bookshelf selectedKb={currentKbName} onSelect={handleSelect} />
        <RawZone />
      </div>
    </>
  )
}
