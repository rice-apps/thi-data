"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { createClientComponentClient } from '@supabase/auth-helpers-nextjs';

interface Table {
  name: string;
  uploadedBy: string;
  dateUploaded: string;
  dateModified: string;
}

const HomeScreen = () => {
  const router = useRouter();
  const supabase = createClientComponentClient();
  const [tables, setTables] = useState<Table[]>([]);
  const [search, setSearch] = useState("");
  const [hoveredTable, setHoveredTable] = useState<string | null>(null);
  const [hover, setHover] = useState(false);

  useEffect(() => {
    fetch("http://localhost:8000/api/tables")
      .then((response) => {
        if (!response.ok) throw new Error("Failed to fetch tables");
        return response.json();
      })
      .then((data: { tables: string[] }) => {
        const tablesWithMeta: Table[] = data.tables.map((tableName) => ({
          name: tableName,
          uploadedBy: "Admin",       
          dateUploaded: "11-21-2025",   
          dateModified: "11-22-2025"   
        }));
        setTables(tablesWithMeta);
      })
      .catch((error) => console.error(error));
  }, []);

    const filteredTables = tables.filter((table) =>
    table?.name?.toLowerCase().includes(search.toLowerCase())
    );

  return (
    <div style={{position: "relative", padding: "2rem", paddingTop: "1rem", fontFamily: "sans-serif" }}>
      <div style={{position: "absolute", top: "1rem", right: "2rem" }}>
        <button
          onClick={async () => {
            await supabase.auth.signOut();
            router.push("/login");
          }}
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        style={{
            padding: "0.4rem 0.8rem",
            borderRadius: "6px",
            border: `1px solid ${hover ? "red" : "#f0b1b1ff"}`,
            backgroundColor: "#fcccccff",
            cursor: "pointer"
            }}
            >
          Sign Out
        </button>
      </div>

      <h1 style={{ fontSize: "1.75rem", marginBottom: "1rem", textAlign: "center" }}>
        Texas Hearing Institute Databases
      </h1>

      <input
        type="text"
        placeholder="Search tables"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{ 
            padding: "0.5rem", 
            fontSize: "1rem", 
            width: "500px", 
            borderRadius: "15px", 
            border: "1px solid #ccc", 
            margin: "0 auto 1rem auto", 
            display: "block" }}
      />

      <div style={{ display: "flex", fontWeight: "bold", padding: "0.5rem 1rem" }}>
        <div style={{ flex: 2 }}>Table Name</div>
        <div style={{ flex: 1 }}>Uploaded By</div>
        <div style={{ flex: 1 }}>Date Uploaded</div>
        <div style={{ flex: 1 }}>Date Modified</div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {filteredTables.map((table) => (
          <div
            key={table.name}
            style={{ backgroundColor: "#cfeff8ff", display: "flex", padding: "0.5rem 1rem", border: hoveredTable === table.name ? "1px solid #1c66bbff" : "1px solid #ddd", borderRadius: "5px", cursor: "pointer"}}
            onMouseEnter={() => setHoveredTable(table.name)}
            onMouseLeave={() => setHoveredTable(null)}
            onClick={() => router.push(`/tables/${table.name}`)}
          >
            <div style={{ flex: 2 }}>{table.name}</div>
            <div style={{ flex: 1 }}>{table.uploadedBy}</div>
            <div style={{ flex: 1 }}>{table.dateUploaded}</div>
            <div style={{ flex: 1 }}>{table.dateModified}</div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default HomeScreen;
