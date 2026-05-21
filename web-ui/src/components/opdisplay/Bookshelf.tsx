import { cn } from "@/lib/utils"

interface Book {
  id: string
  title: string
  category: string
  cover: string
  editing?: boolean
}

const COVER_COLORS = [
  "bg-gradient-to-br from-blue-600 to-blue-800",
  "bg-gradient-to-br from-indigo-600 to-indigo-800",
  "bg-gradient-to-br from-cyan-600 to-cyan-800",
  "bg-gradient-to-br from-amber-600 to-amber-800",
  "bg-gradient-to-br from-rose-600 to-rose-800",
  "bg-gradient-to-br from-emerald-600 to-emerald-800",
  "bg-gradient-to-br from-violet-600 to-violet-800",
  "bg-gradient-to-br from-sky-600 to-sky-800",
]

const DEMO_BOOKS: Record<string, Book[]> = {
  "Project Docs": [
    { id: "1", title: "Backend API", category: "Project Docs", cover: COVER_COLORS[0]! },
    { id: "2", title: "Frontend UI", category: "Project Docs", cover: COVER_COLORS[1]! },
    { id: "3", title: "Deployment", category: "Project Docs", cover: COVER_COLORS[2]! },
    { id: "4", title: "DB Schema", category: "Project Docs", cover: COVER_COLORS[3]! },
  ],
  "Wiki": [
    { id: "5", title: "架构总览", category: "Wiki", cover: COVER_COLORS[4]! },
    { id: "6", title: "API 设计", category: "Wiki", cover: COVER_COLORS[5]! },
    { id: "7", title: "测试指南", category: "Wiki", cover: COVER_COLORS[6]! },
    { id: "8", title: "贡献指南", category: "Wiki", cover: COVER_COLORS[7]! },
  ],
}

export default function Bookshelf() {
  const categories = Object.entries(DEMO_BOOKS)

  return (
    <div className="p-4 space-y-4">
      {categories.map(([cat, books]) => (
        <div key={cat} className="bg-card border border-border rounded-xl p-3">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[10px] font-semibold text-amber-400">📁 {cat}</span>
            <span className="text-[9px] bg-amber-500/10 text-amber-400 px-2 py-0.5 rounded-full">{books.length} books</span>
          </div>

          <div className="grid grid-cols-4 gap-3">
            {books.map(book => (
              <div
                key={book.id}
                className={cn(
                  "group cursor-pointer transition-all duration-200 hover:-translate-y-1",
                  book.editing && "animate-pulse"
                )}
              >
                <div className={cn(
                  "aspect-[3/4] rounded-lg flex items-center justify-center text-[9px] font-medium text-white text-center leading-tight p-2 relative",
                  book.cover
                )}>
                  {book.title}
                  {book.editing && (
                    <span className="absolute top-1 right-1 text-[8px]">✏️</span>
                  )}
                </div>
                <p className="text-[8px] text-muted-foreground mt-1.5 text-center truncate">{book.title}</p>
              </div>
            ))}
            <div className="aspect-[3/4] rounded-lg border border-dashed border-border flex items-center justify-center cursor-pointer hover:border-amber-500/30 transition-colors">
              <span className="text-muted-foreground/40 text-lg">+</span>
            </div>
          </div>
        </div>
      ))}

      <div className="border border-dashed border-border rounded-lg py-2.5 text-center text-[9px] text-muted-foreground/50 cursor-pointer hover:border-amber-500/20 hover:text-amber-400 transition-colors">
        + Add New Category Shelf
      </div>
    </div>
  )
}
