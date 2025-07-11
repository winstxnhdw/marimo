/* Copyright 2024 Marimo. All rights reserved. */
import React, { type JSX, type PropsWithChildren } from "react";
import { z } from "zod";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "../../components/ui/tabs";
import { renderHTML } from "../core/RenderHTML";
import type { IPlugin, IPluginProps } from "../types";

interface Data {
  /**
   * The labels for each tab; raw HTML.
   */
  tabs: string[];
}

// Selected tab index
type T = string;

export class TabsPlugin implements IPlugin<T, Data> {
  tagName = "marimo-tabs";

  validator = z.object({
    tabs: z.array(z.string()),
  });

  render(props: IPluginProps<T, Data>): JSX.Element {
    return (
      <TabComponent
        {...props.data}
        value={props.value}
        setValue={props.setValue}
      >
        {props.children}
      </TabComponent>
    );
  }
}

interface TabComponentProps extends Data {
  value: T;
  setValue: (value: T) => void;
}

const TabComponent = ({
  tabs,
  value,
  setValue,
  children,
}: PropsWithChildren<TabComponentProps>): JSX.Element => {
  // We use the index since labels are raw HTML and can't be used as keys
  // Tabs default to the first tab if the value is not set
  const [internalValue, setInternalValue] = React.useState(value || "0");

  const handleChange = (newValue: T) => {
    setInternalValue(newValue);
    setValue(newValue);
  };

  // Reset the internal value if the value is changed externally
  // and not empty
  if (value !== internalValue && !!value) {
    setInternalValue(value);
  }

  return (
    <Tabs value={internalValue} onValueChange={handleChange}>
      <TabsList>
        {tabs.map((tab, index) => (
          <TabsTrigger key={index} value={index.toString()}>
            {renderHTML({ html: tab })}
          </TabsTrigger>
        ))}
      </TabsList>
      {React.Children.map(children, (child, index) => {
        return <TabsContent value={index.toString()}>{child}</TabsContent>;
      })}
    </Tabs>
  );
};
