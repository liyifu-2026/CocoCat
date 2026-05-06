import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Switch } from "@/components/ui/switch"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Skeleton } from "@/components/ui/skeleton"
import { Separator } from "@/components/ui/separator"
import { Progress } from "@/components/ui/progress"
import { ScrollArea } from "@/components/ui/scroll-area"
import { EmptyState } from "@/components/EmptyState"
import { Users, Settings, Sun, Moon, Activity, Bell } from "lucide-react"

export default function DesignGuide() {
  return (
    <ScrollArea className="h-full">
      <div className="p-8 space-y-8 max-w-4xl">
        <h1 className="text-2xl font-bold">Design Guide</h1>
        <p className="text-muted-foreground text-sm">Component catalog and visual reference</p>

        <Section title="Colors">
          <div className="grid grid-cols-4 gap-3">
            {["background", "foreground", "card", "popover", "primary", "secondary", "muted", "accent", "destructive", "border", "input", "ring", "sidebar"].map(c => (
              <div key={c} className="space-y-1">
                <div className="h-10 rounded-md border" style={{ background: `var(--${c})` }} />
                <div className="text-xs text-muted-foreground">{c}</div>
              </div>
            ))}
          </div>
        </Section>

        <Section title="Buttons">
          <div className="flex flex-wrap gap-2 items-center">
            <Button>Default</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="outline">Outline</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="destructive">Destructive</Button>
            <Button variant="link">Link</Button>
            <Button size="sm">Small</Button>
            <Button size="icon"><Settings className="size-4" /></Button>
            <Button disabled>Disabled</Button>
          </div>
        </Section>

        <Section title="Badges">
          <div className="flex flex-wrap gap-2">
            <Badge>Default</Badge>
            <Badge variant="secondary">Secondary</Badge>
            <Badge variant="outline">Outline</Badge>
            <Badge variant="destructive">Destructive</Badge>
          </div>
        </Section>

        <Section title="Inputs">
          <div className="space-y-3 max-w-sm">
            <Input placeholder="Default input" />
            <Input placeholder="Disabled" disabled />
          </div>
        </Section>

        <Section title="Tabs">
          <Tabs defaultValue="tab1">
            <TabsList>
              <TabsTrigger value="tab1">Tab 1</TabsTrigger>
              <TabsTrigger value="tab2">Tab 2</TabsTrigger>
            </TabsList>
            <TabsContent value="tab1" className="p-4 text-sm text-muted-foreground">Tab 1 content</TabsContent>
            <TabsContent value="tab2" className="p-4 text-sm text-muted-foreground">Tab 2 content</TabsContent>
          </Tabs>
        </Section>

        <Section title="Switch">
          <div className="flex items-center gap-3">
            <Switch />
            <Switch defaultChecked />
          </div>
        </Section>

        <Section title="Skeleton">
          <div className="space-y-3 max-w-sm">
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-20 w-full rounded-lg" />
          </div>
        </Section>

        <Section title="Empty State">
          <div className="border rounded-lg">
            <EmptyState icon={Activity} title="No data" message="Nothing to show here yet." />
          </div>
        </Section>

        <Section title="Avatar">
          <div className="flex gap-3 items-center">
            <Avatar><AvatarFallback>AD</AvatarFallback></Avatar>
            <Avatar className="size-8"><AvatarFallback className="text-xs">CC</AvatarFallback></Avatar>
            <Avatar className="size-6"><AvatarFallback className="text-[10px]">OK</AvatarFallback></Avatar>
          </div>
        </Section>

        <Section title="Progress">
          <Progress value={65} className="w-60" />
        </Section>

        <Section title="Separator">
          <Separator />
        </Section>

        <Section title="Icons">
          <div className="flex flex-wrap gap-4 text-muted-foreground">
            <Users className="size-6" />
            <Settings className="size-6" />
            <Sun className="size-6" />
            <Moon className="size-6" />
            <Activity className="size-6" />
            <Bell className="size-6" />
          </div>
        </Section>
      </div>
    </ScrollArea>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{title}</h2>
      <Card>
        <CardContent className="p-4">{children}</CardContent>
      </Card>
    </section>
  )
}
