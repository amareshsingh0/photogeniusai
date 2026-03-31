import * as React from "react";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Card({ className = "", children, ...props }: CardProps): React.ReactElement {
  return (
    <div
      className={`rounded-xl border border-border bg-card text-card-foreground shadow-sm ${className}`}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className = "", children, ...props }: React.HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return <div className={`flex flex-col space-y-1.5 p-6 ${className}`} {...props}>{children}</div>;
}

export function CardTitle({ className = "", children, ...props }: React.HTMLAttributes<HTMLHeadingElement>): React.ReactElement {
  return <h3 className={`font-semibold leading-none tracking-tight ${className}`} {...props}>{children}</h3>;
}

export function CardContent({ className = "", children, ...props }: React.HTMLAttributes<HTMLDivElement>): React.ReactElement {
  return <div className={`p-6 pt-0 ${className}`} {...props}>{children}</div>;
}
