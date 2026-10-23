import { ButtonDesktop } from "@alfalab/core-components-button/esm/desktop";
import { cva, type VariantProps } from "class-variance-authority";
import {
  type ComponentProps,
  type ElementType,
  isValidElement,
  type ReactElement,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

/*
 * The Alfa-Bank design book button (@alfalab/core-components-button, desktop: no matchMedia, the
 * cabinet is desktop-first) behind the API the screens already use: variant, size, loading, asChild.
 * One `default` (accent, red) button per screen, as in the book.
 */
const VIEW = {
  default: "accent",
  secondary: "secondary",
  ghost: "transparent",
  danger: "outlined",
  link: "text",
} as const;

const SIZE = { default: 40, sm: 32, lg: 48, icon: 40 } as const;

// Only what the core button does not do itself: icon sizes and the danger tone.
const buttonVariants = cva(
  "shrink-0 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "",
        secondary: "",
        ghost: "",
        danger: "!text-status-danger",
        link: "",
      },
      size: { default: "", sm: "", lg: "", icon: "" },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

type ButtonProps = Omit<ComponentProps<"button">, "type"> &
  VariantProps<typeof buttonVariants> & {
    type?: "button" | "submit" | "reset";
    /** Renders the only child (a router Link or an <a>) as the button. */
    asChild?: boolean;
    /** Shows a spinner, disables the button; the label should say what is happening. */
    loading?: boolean;
  };

type LinkLike = { to?: string; href?: string; children?: ReactNode } & Record<string, unknown>;

function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  const common = {
    view: VIEW[variant ?? "default"],
    size: SIZE[size ?? "default"],
    className: cn(buttonVariants({ variant, size }), className),
    "data-slot": "button",
    nowrap: true,
    // The core label is a block: keep an icon next to the text, not above it.
    labelClassName: "inline-flex items-center justify-center gap-2",
  } as const;

  // asChild: the child's element (Link, a) becomes the button's Component; its `to` or `href`
  // travels as `href` (the core button hands it back as `to` to a non-string component).
  if (asChild && isValidElement(children)) {
    const child = children as ReactElement<LinkLike>;
    const { to, href, children: label, ...childProps } = child.props;
    return (
      <ButtonDesktop
        {...common}
        {...(props as Record<string, unknown>)}
        {...childProps}
        Component={child.type as ElementType}
        href={to ?? href}
      >
        {label}
      </ButtonDesktop>
    );
  }

  return (
    <ButtonDesktop
      {...common}
      {...(props as Record<string, unknown>)}
      disabled={disabled || loading}
      loading={loading}
      aria-busy={loading || undefined}
    >
      {children}
    </ButtonDesktop>
  );
}

export { Button, buttonVariants };
